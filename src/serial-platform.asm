; MIT. Robotron glue for the shared N4 / NetDisk engines.
home:   call N3INV
        ld hl,0
        ld (track),hl
        xor a
        ret
serial_position:
        call keyservice
        ld a,(drive)
        cp 2
        jp nc,error
        ld (SEKDSK),a
        ld hl,(track)
        ld a,h
        or a
        jp nz,error
        ld a,l
        cp 160
        jp nc,error
        ld (SEKTRK),hl
        ld hl,(record)
        ld a,h
        or a
        jp nz,error
        ld a,l
        or a
        jp z,error
        cp 41
        jp nc,error
        ld (SEKSEC),a
        ld hl,(dma)
        ld (MEMADR),hl
        xor a
        ret
read:   call serial_position
        or a
        ret nz
        ; One-record requests; no stale cache survives a host reconnect.
        call N3INV
        jp N3READ
write:  call serial_position
        or a
        ret nz
        jp N3WRITE

remote_init:
.ifdef WM_BOOT
        xor a
        out (0fh),a
        ld a,18h
        out (0fh),a
 .ifdef WM_FAST
        ld a,47h
 .else
        ld a,7
 .endif
        out (9),a
        out (0ah),a
 .ifdef WM_FAST
        ld a,WM_FAST
 .else
        ld a,13
 .endif
        out (9),a
        out (0ah),a
        ld a,4
        out (0fh),a
        ld a,44h
        out (0fh),a
        ld a,1
        out (0fh),a
        xor a
        out (0fh),a
        ld a,3
        out (0fh),a
        ld a,0c1h
        out (0fh),a
        ld a,5
        out (0fh),a
        ld a,0eah
        out (0fh),a
.else
        ; Only reset channel B. Keep keyboard A and its clock intact.
        ld a,18h
        out (0fh),a
        ld a,4
        out (0fh),a
        ld a,4dh             ; x16, odd parity, two stop bits
        out (0fh),a
        ld a,3
        out (0fh),a
        ld a,0c1h           ; eight data bits, receiver enabled
        out (0fh),a
        ld a,5
        out (0fh),a
        ld a,0eah           ; eight bits, TX, DTR and RTS
        out (0fh),a
        ld a,05h
        out (9),a
        ld a,1              ; stock ROM CTC-B clock setup
        out (9),a
.endif
        ld hl,remote_state
        ld de,remote_state+1
        ld bc,remote_state_end-remote_state-1
        ld (hl),0
        ldir
        ld hl,net_cache
        ld (N3CACHE),hl
        ld a,3
        call N3ENA
        call rh_enable
        call rh_caps
        or a
        ret nz              ; bounded discovery will retry from CONST
        inc hl
        inc hl              ; capabilities: version, max records, features, reserved
        ld a,(hl)
        ld (RHINPUT),a
        jp rh_config

; SHARED_SERIAL ABI: A byte in/out; carry indicates failure. Preserve
; BC/DE/HL. Begin/finish preserve A too; all polling is finite.
serial_begin:
        push af
        ld a,30h            ; reset SIO receive errors, no FIFO flush
        out (0fh),a
        pop af
        or a
        ret
serial_finish:
        ; Full-duplex RS232 needs no transmitter direction switch.
        or a
        ret
serial_tx:
        push bc
        push af
        ld bc,0
serial_tx_wait:
        in a,(0fh)
        and 4
        jr nz,serial_tx_ready
        dec bc
        ld a,b
        or c
        jr nz,serial_tx_wait
        pop af
        pop bc
        scf
        ret
serial_tx_ready:
        pop af
        out (0dh),a
        pop bc
        or a
        ret
serial_rx:
        push bc
        ld bc,0
serial_rx_wait:
        in a,(0fh)
        and 1
        jr nz,serial_rx_ready
        dec bc
        ld a,b
        or c
        jr nz,serial_rx_wait
        pop bc
        scf
        ret
serial_rx_ready:
        in a,(0dh)
        pop bc
        or a
        ret
