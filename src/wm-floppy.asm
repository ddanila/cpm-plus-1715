; SPDX-License-Identifier: MIT
; 1715M U8272 + UA858 DMA driver, common memory; no bank changes.
; Public calls: C=CP/M drive 2/3, HL=linear track 0..159,
; DE=128-byte record 1..40, IX=common 128-byte buffer. A=0 success.
; Format requires A=A5; ordinary writes require per-drive unlock after verify.
        org 0d000h
        jp fd_init
        jp fd_read
        jp fd_write
        jp fd_format
        jp fd_permission
        jp fd_probe
        jp fd_info
        jp fd_stop
        db 'FDU1'
fd_info:
        ld hl,fd_result
        ld a,(fd_st3)
        ret
fd_stop:
        xor a
        out (28h),a
        ld (fd_motor),a
        ld a,70h
        out (20h),a
        xor a
        ret
fd_permission:
        or a
        jr z,fd_lock
        cp 0a5h
        jp nz,fd_error
        ld a,c
        sub 2
        cp 2
        jp nc,fd_error
        or a
        ld a,1
        jr z,fd_enable
        add a,a
fd_enable:
        ld hl,fd_mask
        or (hl)
        ld (hl),a
        xor a
        ret
fd_lock:xor a
        ld (fd_mask),a
        ret
fd_init:
        di
        ld a,30h
        out (20h),a
        ld a,70h
        out (20h),a
        xor a
        out (28h),a
        ld (fd_motor),a
        xor a
        ld (fd_mask),a
        ld (fd_homed),a
        ld b,4
fd_drain:
        push bc
        ld a,8
        call fd_put
        call fd_get
        call fd_get
        pop bc
        djnz fd_drain
        ld hl,fd_spec
        ld b,3
        call fd_command
        ret
fd_probe:
        call fd_select
        ret nz
        ; 8272 limits one RECALIBRATE to 77 pulses; 80-track drives need
        ; a second attempt when starting at cylinder 78 or 79.
        ld b,2
fd_recalibrate:
        push bc
        ld a,7
        call fd_put
        ld a,(fd_unit)
        call fd_put
        call fd_seek_wait
        pop bc
        jr z,fd_recalibrated
        djnz fd_recalibrate
        ret
fd_recalibrated:
        ld a,4
        call fd_put
        ld a,(fd_unit)
        call fd_put
        call fd_get
        ld (fd_st3),a
        and 30h
        cp 30h
        jp nz,fd_error
        ld a,(fd_unit)
        or a
        ld a,1
        jr z,fd_mark_home
        add a,a
fd_mark_home:
        ld b,a
        ld a,(fd_homed)
        or b
        ld (fd_homed),a
        xor a
        ret
fd_select:
        ld a,c
        sub 2
        cp 2
        jp nc,fd_error
        ld (fd_unit),a
        push af
        ld a,0e0h
        out (20h),a
        pop af
        or a
        ld a,11h
        jr z,fd_motor_set
        ld a,22h
fd_motor_set:
        ld b,a
        ld a,(fd_motor)
        cp b
        jr z,fd_selected
        ld a,b
        out (28h),a
        ld (fd_motor),a
        ; >1 second spin-up at 3.9936 MHz, preserving argument registers.
        push hl
        push de
        ld d,4
fd_spin_outer:
        ld hl,0
fd_spin:dec hl
        ld a,h
        or l
        jr nz,fd_spin
        dec d
        jr nz,fd_spin_outer
        pop de
        pop hl
fd_selected:
        xor a
        ret
fd_position:
        call fd_select
        ret nz
        ; RESET cannot move the head. Establish track zero once per unit
        ; before trusting the controller's relative SEEK counter.
        ld a,(fd_unit)
        or a
        ld a,1
        jr z,fd_home_mask
        add a,a
fd_home_mask:
        ld b,a
        ld a,(fd_homed)
        and b
        jr nz,fd_position_ready
        push hl
        push de
        call fd_probe
        pop de
        pop hl
        ret nz
fd_position_ready:
        ld a,h
        or a
        jp nz,fd_error
        ld a,l
        cp 160
        jp nc,fd_error
        and 1
        ld (fd_head),a
        ld a,l
        srl a
        ld (fd_cyl),a
        ld a,0fh
        call fd_put
        ld a,(fd_unit)
        call fd_put
        ld a,(fd_cyl)
        call fd_put
        jp fd_seek_wait
fd_seek_wait:
        ld b,200
fd_seek_poll:
        push bc
        ld bc,2000
fd_settle:
        dec bc
        ld a,b
        or c
        jr nz,fd_settle
        ld a,8
        call fd_put
        call fd_get
        ld (fd_result),a
        cp 80h
        jr z,fd_seek_next
        call fd_get
        ld (fd_result+1),a
        ld a,(fd_result)
        and 0e0h
        cp 20h
        pop bc
        jp nz,fd_error
        xor a
        ret
fd_seek_next:
        pop bc
        djnz fd_seek_poll
        jp fd_error
fd_read:
        xor a
        jr fd_record
fd_write:
        ld a,c
        sub 2
        cp 2
        jp nc,fd_error
        or a
        ld a,(fd_mask)
        jr z,fd_write_check
        rrca
fd_write_check:
        and 1
        jp z,fd_error
        ld a,1
fd_record:
        ld (fd_writing),a
        ld (fd_record_number),de
        ld (fd_user_buffer),ix
        call fd_position
        ret nz
        ld de,(fd_record_number)
        ld a,d
        or a
        jp nz,fd_error
        ld a,e
        dec a
        cp 40
        jp nc,fd_error
        ld b,a
        and 7
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,fd_buffer
        add hl,de
        ld (fd_slice),hl
        ld a,b
        srl a
        srl a
        srl a
        inc a
        ld (fd_sector),a
        ld a,46h
        call fd_sector_io
        ret nz
        ld hl,(fd_slice)
        ld de,(fd_user_buffer)
        ld bc,128
        ld a,(fd_writing)
        or a
        jr nz,fd_merge
        ldir
        xor a
        ret
fd_merge:
        ex de,hl
        ldir
        ld a,45h
        jp fd_sector_io
fd_sector_io:
        ld (fd_cmd),a
        ld a,(fd_head)
        add a,a
        add a,a
        ld b,a
        ld a,(fd_unit)
        or b
        ld (fd_cmd+1),a
        ld a,(fd_cyl)
        ld (fd_cmd+2),a
        ld a,(fd_head)
        ld (fd_cmd+3),a
        ld a,(fd_sector)
        ld (fd_cmd+4),a
        ld (fd_cmd+6),a
        ld a,(fd_cmd)
        and 1
        ld de,1024
        call fd_dma_setup
        ld hl,fd_cmd
        ld b,9
        call fd_command
        jp nz,fd_dma_error
        jp fd_dma_wait
fd_format:
        cp 0a5h
        jp nz,fd_error
        call fd_position
        ret nz
        ld hl,fd_buffer
        ld b,5
        ld c,1
fd_ids:
        ld a,(fd_cyl)
        ld (hl),a
        inc hl
        ld a,(fd_head)
        ld (hl),a
        inc hl
        ld (hl),c
        inc hl
        ld (hl),3
        inc hl
        inc c
        djnz fd_ids
        ld a,(fd_head)
        add a,a
        add a,a
        ld b,a
        ld a,(fd_unit)
        or b
        ld (fd_fmt+1),a
        ld a,1
        ld de,20
        call fd_dma_setup
        ld hl,fd_fmt
        ld b,6
        call fd_command
        jp nz,fd_dma_error
        jp fd_dma_wait
; Same UA858 defaults as S550: incrementing RAM A, fixed I/O B=41h,
; active-low RDY, EOB interrupt drives the board-gated FDC TC; CPU remains DI.
fd_dma_setup:
        or a
        ld a,79h
        jr z,fd_dma_direction
        ld a,7dh
fd_dma_direction:
        ld (fd_dma+6),a
        dec de
        ld (fd_dma+9),de
        ld hl,fd_dma
        ld b,fd_dma_end-fd_dma
        ld c,0
        otir
        ret
fd_dma_wait:
        ld bc,0
fd_dma_poll:
        in a,(1ch)
        and 0d0h
        cp 0d0h
        jr z,fd_dma_done
        dec bc
        ld a,b
        or c
        jr nz,fd_dma_poll
        ld a,83h
        out (0),a
        ld a,0a3h
        out (0),a
        jp fd_timeout
fd_dma_error:
        ld a,83h
        out (0),a
        ld a,0a3h
        out (0),a
        jp fd_error
fd_dma_done:
        ld a,0bfh
        out (0),a
        in a,(0)
        and 20h
        ld e,a
        ld d,0
        ld a,83h
        out (0),a
        ld a,0a3h
        out (0),a
fd_results:
        ; EOT may report ST1 EN (80h) without TC; accept only exact byte count.
        ld a,d
        or e
        ld (fd_short),a
        ld hl,fd_result
        ld b,7
fd_result_loop:
        push bc
        call fd_get
        ld (hl),a
        inc hl
        pop bc
        djnz fd_result_loop
        ld a,(fd_short)
        or a
        jp nz,fd_error
        ld a,(fd_result+1)
        and 7fh
        jp nz,fd_error
        ld a,(fd_result+2)
        or a
        jp nz,fd_error
        ld a,(fd_result)
        and 0c0h
        cp 80h
        jp nc,fd_error
        xor a
        ret
fd_command:
        ld a,(hl)
        push bc
        call fd_put
        pop bc
        ret nz
        inc hl
        djnz fd_command
        xor a
        ret
fd_put:
        push bc
        push de
        ld e,a
        ld bc,0
fd_put_poll:
        in a,(1ch)
        and 0c0h
        cp 80h
        jr z,fd_put_ready
        dec bc
        ld a,b
        or c
        jr nz,fd_put_poll
        pop de
        pop bc
        jp fd_timeout
fd_put_ready:
        ld a,e
        out (1dh),a
        pop de
        pop bc
        xor a
        ret
fd_get:
        push bc
        ld bc,0
fd_get_poll:
        in a,(1ch)
        and 0c0h
        cp 0c0h
        jr z,fd_get_ready
        dec bc
        ld a,b
        or c
        jr nz,fd_get_poll
        pop bc
        jp fd_timeout
fd_get_ready:
        in a,(1dh)
        pop bc
        ret
fd_timeout:
        in a,(1ch)
        ld (fd_result+1),a
        ld a,e
        ld (fd_result+2),a
        ld a,d
        ld (fd_result+3),a
        ld a,0eeh
        ld (fd_result),a
fd_error:
        ld a,1
        or a
        ret
fd_dma: db 0c3h,0c3h,0c3h,0c3h,0c3h,0c3h
        db 79h
        dw fd_buffer,1023
        db 14h,28h,95h,41h,12h,14h,82h,0cfh,0abh,87h
fd_dma_end:
fd_spec: db 3,0dfh,2
fd_cmd: db 46h,0,0,0,1,3,1,1bh,0ffh
fd_fmt: db 4dh,0,3,5,54h,0e5h
fd_mask: db 0
fd_homed: db 0
fd_motor: db 0
fd_unit: db 0
fd_head: db 0
fd_cyl: db 0
fd_sector: db 1
fd_st3: db 0
fd_writing: db 0
fd_short: db 0
fd_record_number: dw 0
fd_user_buffer: dw 0
fd_slice: dw 0
fd_result: ds 7
fd_end:
        if fd_end > 0dc00h
        error 'floppy driver overlaps sector buffer'
        endif
fd_buffer equ 0dc00h
