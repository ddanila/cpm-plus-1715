; SPDX-License-Identifier: MIT
; Destructive B: acceptance diagnostic, injected only into private test images.
        org 100h
        ld sp,stack
        ld c,45
        ld e,0ffh
        call 5
        call erase_all
        xor a
        ld (index),a
next_file:
        call clear_fcb
        ld a,(index)
        and 15
        add a,'A'
        ld (fcb+1),a
        ld a,(index)
        rrca
        rrca
        rrca
        rrca
        and 3
        add a,'0'
        ld (fcb+2),a
        ld de,fcb
        ld c,22
        call 5
        cp 0ffh
        jp z,failed
        call close
        ld a,(index)
        inc a
        ld (index),a
        cp 64
        jr nz,next_file
        call clear_fcb
        ld de,fcb
        ld c,22
        call 5
        cp 0ffh
        jp nz,failed
        call erase_all
        call clear_fcb
        ld de,fcb
        ld c,22
        call 5
        cp 0ffh
        jp z,failed
        ld hl,0
        ld (number),hl
write_record:
        ld a,(number)
        ld hl,buffer
        ld b,128
pattern:ld (hl),a
        inc a
        inc hl
        djnz pattern
        ld de,buffer
        ld c,26
        call 5
        ld de,fcb
        ld c,21
        call 5
        or a
        jr nz,full
        ld hl,(number)
        inc hl
        ld (number),hl
        ld de,753
        or a
        sbc hl,de
        jp nc,failed
        jr write_record
full:   cp 2
        jp nz,failed
        ld hl,(number)
        ld de,752
        or a
        sbc hl,de
        jp nz,failed
        call close
        call clear_fcb
        ld de,fcb
        ld c,15
        call 5
        cp 0ffh
        jp z,failed
        ld hl,0
        ld (number),hl
read_record:
        ld hl,(number)
        ld (fcb+33),hl
        xor a
        ld (fcb+35),a
        ld de,fcb
        ld c,33
        call 5
        or a
        jp nz,failed
        ld a,(number)
        ld hl,buffer
        ld b,128
check:  cp (hl)
        jp nz,failed
        inc a
        inc hl
        djnz check
        ld hl,(number)
        inc hl
        ld (number),hl
        ld de,752
        or a
        sbc hl,de
        jr nz,read_record
        call close
        call erase_all
        call clear_fcb
        ld de,fcb
        ld c,22
        call 5
        cp 0ffh
        jp z,failed
        call close
        call erase_all
        ld de,pass
        jr finish
failed: ld de,fail
finish: ld c,9
        call 5
        jp 0
clear_fcb:
        ld hl,fcb
        ld de,fcb+1
        ld bc,35
        ld (hl),0
        ldir
        ld hl,name
        ld de,fcb+1
        ld bc,11
        ldir
        ld a,2
        ld (fcb),a
        ret
close:  ld de,fcb
        ld c,16
        call 5
        cp 0ffh
        jp z,failed
        ret
erase_all:
        call clear_fcb
        ld hl,fcb+1
        ld b,11
wild:   ld (hl),'?'
        inc hl
        djnz wild
        ld de,fcb
        ld c,19
        jp 5
name: db 'BANKTESTBIN'
pass: db 'BANKED DISK PASS',13,10,'$'
fail: db 'BANKED DISK FAIL',13,10,'$'
index: db 0
number: dw 0
fcb: ds 36
buffer: ds 128
        ds 128
stack:
