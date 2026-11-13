; SPDX-License-Identifier: MIT
; Relocate into unused common scratch before testing the entire advertised TPA.
        org 100h
        ld hl,body
        ld de,0f700h
        ld bc,body_end-body
        ldir
        jp 0f700h
body:
        phase 0f700h
        ld sp,0f700h
        ld hl,(6)
        ld l,0
        ld a,h
        cp 0bah
        jr c,failed
        ld de,0100h
        or a
        sbc hl,de
        ld b,h
        ld c,l
        ld (count),bc
        ld hl,0100h
fill:   ld a,h
        xor l
        ld (hl),a
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,fill
        ld bc,(count)
        ld hl,0100h
verify: ld a,h
        xor l
        cp (hl)
        jr nz,failed
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,verify
        ld de,passed
        jr print
failed: ld de,failure
print:  ld c,9
        call 5
        jp 0
count:  dw 0
passed: db 'BANKED TPA PASS',13,10,'$'
failure:db 'BANKED TPA FAIL',13,10,'$'
        dephase
body_end:
