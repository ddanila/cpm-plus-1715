; SPDX-License-Identifier: MIT
; Portable CP/M 2+ diagnostic. All disk access uses BDOS, never direct ports.
        org 100h
        ld (oldsp),sp
        ld sp,stacktop
        ld de,banner
        call print
        ld a,(80h)
        or a
        jp z,info
        ld hl,81h
skip:   ld a,(hl)
        cp ' '
        jr nz,command
        inc hl
        jr skip
command:
        and 0dfh
        cp 'W'
        jp z,write_test
        cp 'R'
        jp z,read_test
        cp 'C'
        jp z,cleanup
        cp 'K'
        jp z,keyboard
        cp 'I'
        jp z,info
        ld de,usage
        jp finish
info:   ld c,12
        call 5
        ld a,h
        call hexbyte
        ld a,l
        call hexbyte
        ld de,info_ok
        jp finish
write_test:
        call reset_fcb
        ld c,15
        ld de,fcb
        call bdos
        cp 0ffh
        jp nz,collision
        call reset_fcb
        ld c,22
        ld de,fcb
        call bdos
        cp 0ffh
        jp z,iofail
        xor a
        ld (record),a
write_loop:
        call pattern
        call dma
        ld c,21
        ld de,fcb
        call bdos
        or a
        jp nz,writefail
        ld a,(record)
        inc a
        ld (record),a
        jr nz,write_loop
        call close
        jp nz,iofail
        ld de,write_ok
        jp finish
read_test:
        call verify
        jp nz,verifyfail
        ld de,read_ok
        jp finish
cleanup:
        call verify
        jp nz,verifyfail
        call reset_fcb
        ld c,19
        ld de,fcb
        call bdos
        cp 0ffh
        jp z,iofail
        ld de,clean_ok
        jp finish
keyboard:
        ld de,key_prompt
        call print
        ld c,1
        call bdos
        ld de,key_ok
        jp finish
; Verify exact 256-record length, then random reads in reverse order.
verify:
        call reset_fcb
        ld c,15
        ld de,fcb
        call bdos
        cp 0ffh
        jr z,bad
        ld c,35
        ld de,fcb
        call bdos
        ld a,(fcb+33)
        or a
        jr nz,verify_bad
        ld a,(fcb+34)
        cp 1
        jr nz,verify_bad
        ld a,(fcb+35)
        or a
        jr nz,verify_bad
        ld a,255
        ld (record),a
verify_loop:
        call pattern
        ld a,(record)
        ld (fcb+33),a
        xor a
        ld (fcb+34),a
        ld (fcb+35),a
        ld de,readbuf
        ld c,26
        call bdos
        ld de,fcb
        ld c,33
        call bdos
        or a
        jr nz,verify_bad
        ld hl,buffer
        ld de,readbuf
        ld b,128
compare:
        ld a,(de)
        cp (hl)
        jr nz,verify_bad
        inc hl
        inc de
        djnz compare
        ld a,(record)
        sub 1
        ld (record),a
        jr nc,verify_loop
        call close
        ret
verify_bad:
        call close
bad:    ld a,1
        or a
        ret
pattern:
        ld hl,buffer
        ld b,128
        ld c,0
pattern_loop:
        ld a,(record)
        xor c
        ld (hl),a
        inc hl
        inc c
        djnz pattern_loop
        ld a,(record)
        or a
        ret nz
        ld hl,signature
        ld de,buffer
        ld bc,16
        ldir
        ret
dma:    ld c,26
        ld de,buffer
        jp bdos
close:  ld c,16
        ld de,fcb
        call bdos
        cp 0ffh
        jr z,bad
        xor a
        ret
reset_fcb:
        ld hl,fcb
        ld de,fcb+1
        ld bc,35
        ld (hl),0
        ldir
        ld hl,filename
        ld de,fcb+1
        ld bc,11
        ldir
        ret
bdos:   push bc
        push de
        push hl
        call 5
        pop hl
        pop de
        pop bc
        ret
print:  ld c,9
        jp bdos
hexbyte:
        push af
        rrca
        rrca
        rrca
        rrca
        call nibble
        pop af
nibble: and 15
        add a,'0'
        cp '9'+1
        jr c,hexout
        add a,7
hexout: ld e,a
        ld c,2
        jp bdos
writefail:
        call close
iofail: ld de,io_error
        jp finish
verifyfail:
        ld de,verify_error
        jp finish
collision:
        call close
        ld de,exists_error
finish: call print
        ld sp,(oldsp)
        ret
banner: db 'P1715TEST v1 CP/M BDOS=', '$'
info_ok: db 13,10,'P1715TEST INFO PASS',13,10,'W=create 32KiB scratch; R=verify after cold boot; C=verify+delete; K=keyboard',13,10,'$'
usage: db 13,10,'Usage: P1715TST [I|W|R|C|K]',13,10,'$'
write_ok: db 13,10,'P1715TEST WRITE PASS records=256; cold boot then R',13,10,'$'
read_ok: db 13,10,'P1715TEST VERIFY PASS records=256',13,10,'$'
clean_ok: db 13,10,'P1715TEST CLEAN PASS',13,10,'$'
key_prompt: db 13,10,'Press one key; visually check the echo: $'
key_ok: db 13,10,'P1715TEST KEYBOARD OBSERVED (operator must assess echo)',13,10,'$'
io_error: db 13,10,'P1715TEST IO FAIL (partial scratch may remain)',13,10,'$'
verify_error: db 13,10,'P1715TEST VERIFY FAIL; file retained',13,10,'$'
exists_error: db 13,10,'P1715TEST COLLISION FAIL; file retained',13,10,'$'
filename: db 'P1715TSTDAT'
        ; CP/M filename must occupy exactly 11 bytes: 8 name + 3 extension.
signature: db 'P1715TEST-v1',0,1,2,3
oldsp:  dw 0
record: db 0
fcb:    ds 36
buffer: ds 128
readbuf: ds 128
        ds 128
stacktop:
