; SPDX-License-Identifier: MIT
; PC001 W4 + banked 62400 platform diagnostic. No floppy accesses.
; Scratch: F700..F70A (saved), application 4000..9FFF.
; Status reads acknowledge controller sticky flags. Geometry is never changed.
        org 100h
        ld hl,0e000h
        ld de,signature
        ld b,32
 guard: ld a,(de)
        cp (hl)
        jp nz,unsupported
        inc hl
        inc de
        djnz guard
        in a,(19h)
        ld (initial),a
        and 44h
        cp 4
        jp nz,unsupported
        di
        ld hl,0f700h
        ld de,saved_code
        ld bc,tramp_end-tramp
        ldir
        ld hl,tramp
        ld de,0f700h
        ld bc,tramp_end-tramp
        ldir
        ; Preserve both windows before stopping display or writing any byte.
        ld hl,2000h
        ld de,8000h
        call read_windows
        ld a,40h
        out (19h),a
        in a,(19h)
        ld (stopped),a
        and 4
        call nz,fail
        ld a,0
        call pattern
        ld a,0ffh
        call pattern
        ; Always restore both windows, including on verification failure.
        ld hl,8000h
        ld de,2000h
        call write_windows
        ld hl,2000h
        ld de,6000h
        call read_windows
        ld hl,8000h
        ld de,6000h
        call compare
        ld a,20h
        out (19h),a
        ld a,0c0h
        out (19h),a
        in a,(19h)
        ld (restarted),a
        and 44h
        cp 4
        call nz,fail
        ld hl,saved_code
        ld de,0f700h
        ld bc,tramp_end-tramp
        ldir
        ld de,status_msg
        call puts
        ld a,(initial)
        call hex
        ld a,(stopped)
        call hex
        ld a,(restarted)
        call hex
        ld de,passed
        ld a,(errors)
        or a
        jr z,finish
        ld de,failed
finish: call puts
        jp 0
unsupported:
        ld de,unsupported_msg
        jr finish
pattern:
        ld (mask),a
        ld hl,4000h
        ld bc,2000h
fill:   ld a,(mask)
        xor h
        xor l
        ld (hl),a
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,fill
        ld hl,4000h
        ld de,2000h
        call write_windows
        ld hl,2000h
        ld de,6000h
        call read_windows
        ; PC001 observation: video A11 is not decoded. Upper half wins
        ; when writing the whole window; both halves must read identically.
        ld hl,5800h
        ld de,5000h
        ld bc,0800h
        ldir
        ld hl,4000h
        ld de,6000h
        call compare
        ; Reverse direction: write lower half only, verify both aliases.
        ld hl,5000h
        ld bc,1000h
flip:   ld a,(hl)
        xor 8
        ld (hl),a
        inc hl
        dec bc
        ld a,b
        or c
        jr nz,flip
        ld hl,5000h
        ld de,3000h
        ld bc,0800h
        ld a,02h
        call 0f700h
        ld hl,2000h
        ld de,6000h
        call read_windows
        ld hl,4000h
        ld de,6000h
compare:
        ld bc,2000h
check:  ld a,(de)
        cp (hl)
        jr nz,mismatch
        inc hl
        inc de
        dec bc
        ld a,b
        or c
        jr nz,check
        ret
mismatch:
        push hl
        push de
        ld de,mismatch_msg
        call puts
        pop de
        pop hl
        push hl
        push de
        ld a,h
        call hex
        pop de
        pop hl
        push hl
        push de
        ld a,l
        call hex
        pop de
        pop hl
        push hl
        push de
        ld a,(hl)
        call hex
        pop de
        pop hl
        ld a,(de)
        call hex
        ld de,newline
        call puts
fail:   ld a,1
        ld (errors),a
        ret
read_windows:
        ld a,20h
        jr transfer
write_windows:
        ld a,02h
transfer:
        ld bc,2000h
        jp 0f700h
tramp:  out (24h),a
        ldir
        ld a,22h
        out (24h),a
        ret
tramp_end:
puts:   ld c,9
        jp 5
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
signature:
        include 'build/video-signature.inc'
initial: db 0
stopped: db 0
restarted: db 0
errors: db 0
mask: db 0
saved_code: ds tramp_end-tramp
mismatch_msg: db 'Mismatch expected-buffer address high/low, expected/actual: $'
newline: db 13,10,'$'
status_msg: db '8275 initial/stopped/restarted: $'
passed: db 13,10,'VIDEO RAM PASS: 4096 char + 2048 screen (mirrored), two patterns + bidirectional alias, restored',13,10,'$'
failed: db 13,10,'VIDEO FAIL: memory/status or restoration mismatch',13,10,'$'
unsupported_msg: db 'VIDEO SKIP: requires qualified banked 62400 platform and W4 display state',13,10,'$'
