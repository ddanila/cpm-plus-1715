; SPDX-License-Identifier: MIT. FORMAT C ERASE / D ERASE / C PROBE / C LOCK.
; Requires resident FDU1 driver. Never formats serial or RAM disks.
        org 100h
        ld hl,0d018h
        ld de,signature
        ld b,4
check_driver:
        ld a,(de)
        cp (hl)
        jp nz,unsupported
        inc hl
        inc de
        djnz check_driver
        ld a,(80h)
        cp 7
        jp c,usage
        ld hl,81h
spaces: ld a,(hl)
        cp ' '
        jr nz,drive
        inc hl
        jr spaces
drive:  sub 'C'
        cp 2
        jp nc,usage
        add a,2
        ld (selected),a
        inc hl
        ld a,(hl)
        cp ' '
        jp nz,usage
        inc hl
        ld de,erase_word
        call word
        jr z,erase
        ld de,probe_word
        call word
        jr z,probe
        ld de,lock_word
        call word
        jp nz,usage
        xor a
        call 0d00ch
        call 0d015h
        ld de,locked
        jp print_exit
word:   push hl
word_loop:
        ld a,(de)
        or a
        jr z,word_end
        cp (hl)
        jr nz,word_return
        inc hl
        inc de
        jr word_loop
word_end:
        ld a,(hl)
        or a
        jr z,word_return
        cp 13
word_return:
        pop hl
        ret
probe:  ld a,(selected)
        ld c,a
        call 0d00fh
        or a
        jp nz,failure
        call 0d015h
        ld de,probe_ok
        jp print_exit
erase:  xor a
        call 0d00ch
        ld a,(selected)
        ld c,a
        call 0d00fh
        or a
        jp nz,failure
        ld de,starting
        call puts
        xor a
        ld (track),a
next_track:
        xor a
        ld (record),a
        ld a,(selected)
        ld c,a
        ld a,(track)
        ld l,a
        ld h,0
        ld a,0a5h
        call 0d009h
        or a
        jp nz,failure
        ld a,1
        ld (record),a
verify_sector:
        ld a,(selected)
        ld c,a
        ld a,(track)
        ld l,a
        ld h,0
        ld a,(record)
        ld e,a
        ld d,0
        ld ix,8000h
        call 0d003h
        or a
        jp nz,failure
        ld hl,0dc00h
        ld bc,1024
verify_byte:
        ld a,(hl)
        cp 0e5h
        jp nz,failure
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,verify_byte
        ld a,(record)
        add a,8
        ld (record),a
        cp 41
        jr c,verify_sector
        ld c,2
        ld e,'.'
        call 5
        ld a,(track)
        inc a
        ld (track),a
        cp 160
        jp c,next_track
        ld a,(selected)
        ld c,a
        ld a,0a5h
        call 0d00ch
        call 0d015h
        ld c,13
        call 5
        ld de,passed
        jp print_exit
failure:
        xor a
        call 0d00ch
        call 0d015h
        ld de,failed
        call puts
        ld a,(track)
        call hex
        ld a,(record)
        call hex
        call 0d012h
        call hex_saved_hl
        ld b,7
print_results:
        ld a,(hl)
        push bc
        call hex_saved_hl
        pop bc
        inc hl
        djnz print_results
        ld de,newline
        jp print_exit
hex_saved_hl:
        push hl
        call hex
        pop hl
        ret
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
unsupported: ld de,unsupported_msg
        jr print_exit
usage:  ld de,usage_msg
print_exit:
        call puts
        jp 0
puts:   ld c,9
        jp 5
signature: db 'FDU1'
erase_word: db 'ERASE',0
probe_word: db 'PROBE',0
lock_word: db 'LOCK',0
selected: db 2
track: db 0
record: db 0
starting: db 'Erasing and verifying 80 cylinders, 2 heads, 5 x 1024 bytes',13,10,'$'
passed: db 13,10,'FORMAT PASS: 800 KiB verified; selected floppy writes enabled.',13,10,'$'
failed: db 13,10,'FORMAT FAIL; physical writes locked. Track/record/ST3/results: $'
locked: db 'Physical writes locked.',13,10,'$'
probe_ok: db 'Drive ready; recalibration passed. No data written.',13,10,'$'
unsupported_msg: db 'FDU1 resident driver required.',13,10,'$'
usage_msg: db 'FORMAT C|D ERASE|PROBE|LOCK',13,10,'$'
newline: db 13,10,'$'
