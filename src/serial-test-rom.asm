; MIT. Public serial bootstrap fixture, not a hardware replacement ROM.
; Implements only Ravi's documented LOAD/EXEC subset with ordinary Z80 I/O.
        org 0
        di
        ld hl,0
        ld de,0
        ld bc,2048
        ldir
        out (28h),a
        ld sp,0990h
        ld a,18h
        out (0fh),a
        ld a,4
        out (0fh),a
        ld a,4dh
        out (0fh),a
        ld a,3
        out (0fh),a
        ld a,0c1h
        out (0fh),a
        ld a,5
        out (0fh),a
        ld a,68h
        out (0fh),a
sync:   call rx
        cp 11h
        jr nz,sync
        call rx
        cp 11h
        jr nz,sync
        ld a,12h
        call tx
        ld a,12h
        call tx
command: call rx
        cp 0ah
        jr z,load
        cp 0aah
        jr nz,command
        call word
        jp (hl)
load:   call word
        ex de,hl
        call word
        ld b,h
        ld c,l
loadbyte: call rx
        ld (de),a
        inc de
        dec bc
        ld a,b
        or c
        jr nz,loadbyte
        jr command
word:   call rx
        ld l,a
        call rx
        ld h,a
        ret
rx:     in a,(0fh)
        and 1
        jr z,rx
        in a,(0dh)
        ret
tx:     push af
txwait: in a,(0fh)
        and 4
        jr z,txwait
        pop af
        out (0dh),a
        ret
        ds 2048-$,0
