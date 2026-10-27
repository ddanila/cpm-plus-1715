; SPDX-License-Identifier: MIT
; Guest BDOS regression: actual four-record I/O, reverse random reads and USER.
        org 100h
        ld c,32
        ld e,1
        call 5
        ld de,fcb
        ld c,22
        call 5
        cp 0ffh
        jp z,fail
        ld hl,buffer
        ld bc,512
        xor a
fill:   ld (hl),a
        inc hl
        inc a
        dec bc
        ld d,a
        ld a,b
        or c
        ld a,d
        jr nz,fill
        ld de,buffer
        ld c,26
        call 5
        ld e,4
        ld c,44
        call 5
        ld de,fcb
        ld c,21
        call 5
        or a
        jp nz,fail
        ld de,fcb
        ld c,16
        call 5
        cp 0ffh
        jp z,fail
        xor a
        ld (fcb+32),a
        ld de,fcb
        ld c,15
        call 5
        cp 0ffh
        jp z,fail
        ld de,readbuf
        ld c,26
        call 5
        ld de,fcb
        ld c,20
        call 5
        or a
        jp nz,fail
        ld hl,buffer
        ld de,readbuf
        ld bc,512
compare: ld a,(de)
        cp (hl)
        jp nz,fail
        inc hl
        inc de
        dec bc
        ld a,b
        or c
        jr nz,compare
        ld e,1
        ld c,44
        call 5
        ld a,3
random: ld (fcb+33),a
        ld de,fcb
        ld c,33
        call 5
        or a
        jp nz,fail
        ld a,(fcb+33)
        and 1
        rrca
        ld hl,readbuf
        ld b,128
check:  cp (hl)
        jp nz,fail
        inc hl
        inc a
        djnz check
        ld a,(fcb+33)
        dec a
        jp p,random
        ld de,fcb
        ld c,16
        call 5
        ld c,32
        ld e,0
        call 5
        ld de,fcb
        ld c,15
        call 5
        cp 0ffh
        jp nz,fail
        ld de,ok
        jr print
fail:   ld de,bad
print:  ld c,9
        call 5
        jp 0
ok:     db 'CPM1715 MULTI RANDOM USER OK',13,10,'$'
bad:    db 'CPM1715 RELIABILITY FAILED',13,10,'$'
fcb:    db 0,'USERTESTBIN'
        ds 24,0
buffer: ds 512,0
readbuf: ds 512,0
