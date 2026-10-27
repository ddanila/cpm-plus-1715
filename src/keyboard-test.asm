; SPDX-License-Identifier: MIT
; Direct BIOS disk workload deliberately avoids BDOS console polling while
; input arrives. All input and disk data travel through the ordinary guest BIOS.
        include 'build/keyboard.inc'
        org 100h
        jp start
mode:   db 0            ; 0 accumulate; 1 overflow/recover; 2 stream; 3 warm boot
wanted: dw 64           ; complete decoded characters after program entry
start:  ld hl,(keydecoded)
        ld (baseline),hl
        ld hl,received
        ld (nextout),hl
        ld bc,256
        ld (hl),0
        ld de,received+1
        dec bc
        ldir
        ld bc,0
        call 0bc1bh     ; SELDSK A
        ld hl,156
        ld (tracknum),hl
again:  ld bc,(tracknum)
        call 0bc1eh     ; SETTRK
        ld bc,1
        call 0bc21h     ; SETSEC
        ld bc,sectorbuf
        call 0bc24h     ; SETDMA
        call 0bc27h     ; READ
        or a
        jp nz,fail
        ld bc,0
        call 0bc2ah     ; WRITE identical data, exercising the full RMW path
        or a
        jp nz,fail
        ld a,(tracknum)
        xor 1
        ld (tracknum),a
        ld a,(mode)
        cp 2
        jr nz,checkdecoded
stream: call 0bc06h     ; CONST
        or a
        jr z,checkdecoded
        call collect
        jr stream
checkdecoded:
        ld hl,(keydecoded)
        ld de,(baseline)
        or a
        sbc hl,de
        ld de,(wanted)
        or a
        sbc hl,de
        jp c,again
        ld a,(mode)
        cp 3
        jp z,0         ; preserve complete queued command across warm boot
        cp 2
        jr z,save
        ld a,(keycount)
        ld b,a
        or a
        jr z,save
remaining:
        push bc
        call collect
        pop bc
        djnz remaining
        ld a,(mode)
        cp 1
        jr nz,save
        ld b,16
recover:
        push bc
        call collect
        pop bc
        djnz recover
save:   ld bc,159
        call 0bc1eh
        ld bc,9        ; reserved host-allocated KBDOUT.BIN, block 388
        call 0bc21h
        ld bc,received
        call 0bc24h
        ld bc,0
        call 0bc2ah
        or a
        jr nz,fail
        ld bc,10
        call 0bc21h
        ld bc,received+128
        call 0bc24h
        ld bc,0
        call 0bc2ah
        or a
        jr nz,fail
        ld de,ok
        jr print
collect:
        call 0bc09h    ; CONIN, raw controls included
        ld hl,(nextout)
        ld (hl),a
        inc hl
        ld (nextout),hl
        ret
fail:   ld de,bad
print:  ld c,9
        call 5
        jp 0
ok:     db 'CPM1715 ASYNC KEYBOARD OK',13,10,'$'
bad:    db 'CPM1715 ASYNC KEYBOARD FAILED',13,10,'$'
baseline: dw 0
tracknum: dw 0
nextout: dw 0
sectorbuf: ds 128,0
received: ds 256,0
