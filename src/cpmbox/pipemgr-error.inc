; Resident failure exit: no chain, no interactive disk error prompt. Only the
; reserved A:user0 pipe files are removed; named output files are retained.
boxioerror:
 ld sp,inbuf+7fh
 call uhookwb
 xor a
 ld (awake),a
 ld (PipedO),a
 ld (PipedI),a
 ld (inflg),a
 dec a
 ld (delete),a
 ld c,ERRMODE
 ld e,0feh
 call fdos
 ld de,boxerrmsg
 call print
 call boxcleanup
 rst 0
boxcleanup:
 ld iy,boxtmpin
 ld c,DELETEF
 call fcbdos
 ld iy,boxtmpout
 ld c,DELETEF
 call fcbdos
 ret
 dseg
boxerrmsg: defb 13,10,'PIPEMGR: I/O failed; pipeline cancelled',13,10,'$'
boxtmpin: defb 1
 defm 'PIPEIN  $$$'
 defs 25
 defb 1
boxtmpout: defb 1
 defm 'PIPEOUT $$$'
 defs 25
 defb 1
 cseg

; Validate the next transient before CHAIN. Otherwise a missing command leaves
; CCP reading the pipe as its console, repeatedly printing prompts at EOF.
boxchecknext:
 ld hl,pipenxt
boxskipspace:
 ld a,(hl)
 cp ' '
 jr nz,boxparsecmd
 inc hl
 jr boxskipspace
boxparsecmd:
 ld (boxparse),hl
 ld de,boxparse
 ld c,PARSEFN
 call fdos
 ld a,h
 and l
 inc a
 jp z,boxnextfail
 ld a,(boxcmd)
 cp 2
 jp nc,boxnextfail
 ld hl,boxcmd+1
 ld b,11
boxwild:
 ld a,(hl)
 cp '?'
 jp z,boxnextfail
 inc hl
 djnz boxwild
 ld a,(boxcmd+9)
 cp ' '
 jr nz,boxcmdopen
 ld hl,boxcmd+9
 ld (hl),'C'
 inc hl
 ld (hl),'O'
 inc hl
 ld (hl),'M'
boxcmdopen:
 ld iy,boxcmd
 ld c,OPENF
 call fcbdos
 inc a
 jp z,boxnextfail
 ld c,CLOSEF
 call fcbdos
 inc a
 jp z,boxnextfail
 ret
boxnextfail:
 ld de,boxcmdmsg
 call print
 jp boxioerror
 dseg
boxparse: defw pipenxt,boxcmd
boxcmd: defs 38
boxcmdmsg: defb 13,10,'PIPEMGR: next command unavailable',13,10,'$'
 cseg
