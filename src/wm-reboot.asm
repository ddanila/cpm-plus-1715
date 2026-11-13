; SPDX-License-Identifier: MIT. Bench-only 62400 RAM reload, no ROM changes.
; Run with matching new CPM3.SYS already installed on the serial system disk.
        org 100h
        di
        ld hl,copy_code
        ld de,0f700h
        ld bc,copy_end-copy_code
        ldir
        ld hl,payload
        ld de,0e000h
        ld bc,payload_end-payload
        jp 0f700h
copy_code:
        ldir
        jp 0e033h
copy_end:
payload:
        incbin 'build/banked/platform-62400.cim'
payload_end:
