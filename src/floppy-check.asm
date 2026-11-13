; SPDX-License-Identifier: MIT. Temporary RAM driver check for qualified PC001.
        org 100h
        di
        ld hl,payload
        ld de,0d000h
        ld bc,payload_end-payload
        ldir
        call 0d000h
        ld de,init_msg
        call status
        ld c,2
        call 0d00fh
        ld de,probe_msg
        call status
        call 0d012h
        push hl
        call hex
        pop hl
        ld b,7
results:
        push hl
        push bc
        ld a,(hl)
        call hex
        pop bc
        pop hl
        inc hl
        djnz results
        call 0d015h
        ld de,done
        ld c,9
        call 5
        jp 0
status: push af
        ld c,9
        call 5
        pop af
        call hex
        in a,(1ch)
        jp hex
hex:    push af
        rrca
        rrca
        rrca
        rrca
        call nibble
        pop af
        call nibble
        ld e,' '
        ld c,2
        jp 5
nibble: and 0fh
        add a,'0'
        cp '9'+1
        jr c,digit
        add a,7
digit:  ld e,a
        ld c,2
        jp 5
init_msg: db 'FDU init return/MSR: $'
probe_msg: db 13,10,'C probe return/MSR, ST3, result: $'
done: db 13,10,'Motor off; no disk data written.',13,10,'$'
payload:
        incbin 'build/wm-floppy.cim'
payload_end:
