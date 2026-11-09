; Qualification-only, no RSX attached: report the loader's BDOS/TPA vector.
 org 100h
 ld de,message
 ld c,9
 call 5
 ld hl,(6)
 ld a,h
 call byte
 ld a,l
 call byte
 ld de,newline
 ld c,9
 call 5
 ret
byte:
 push hl
 push af
 rrca
 rrca
 rrca
 rrca
 call nibble
 pop af
 call nibble
 pop hl
 ret
nibble:
 and 15
 add a,'0'
 cp '9'+1
 jr c,emit
 add a,7
emit:
 ld e,a
 ld c,2
 jp 5
message: db 'TPA=$'
newline: db 13,10,'$'
