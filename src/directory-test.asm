; SPDX-License-Identifier: MIT
        org 100h
        ld de,fcb
        ld c,22
        call 5
        cp 0ffh
        ld de,bad
        jr nz,print
        ld de,ok
print:  ld c,9
        call 5
        jp 0
ok:     db 'CPM1715 DIRECTORY FULL OK',13,10,'$'
bad:    db 'CPM1715 DIRECTORY FULL FAILED',13,10,'$'
fcb:    db 0,'NOFREE  TXT'
        ds 24,0
