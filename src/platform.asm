; SPDX-License-Identifier: MIT
; Copyright (c) 2026 Danila Sukharev
; Original classic 1715 hardware services. No historical BIOS code included.
        include "build/system.inc"
        org 0c000h
        jp unavailable
        jp home
        jp const
        jp conin
        jp conout
        jp unavailable
        jp unavailable
        jp unavailable
        jp home
        jp seldsk
        jp settrk
        jp setsec
        jp setdma
        jp read
        jp write
        jp unavailable
        jp sectrn
        jp loader
init:   di
        ld a,0efh
        out (20h),a
        ld a,0fh
        out (1),a
        ld a,4fh
        out (3),a
        ld a,3
        out (5),a
        ld a,0cfh
        out (7),a
        ld a,0e3h
        out (7),a
        ld a,3
        out (7),a
        ld a,4
        out (6),a
        ld a,0a5h
        out (4),a
        ; SIO A: reset, x16 asynchronous 8-bit receiver, no interrupts.
        ld a,18h
        out (0eh),a
        ld a,4
        out (0eh),a
        ld a,44h
        out (0eh),a
        ld a,3
        out (0eh),a
        ld a,0c1h
        out (0eh),a
        ld a,5
        out (0eh),a
        ld a,68h
        out (0eh),a
        ld a,47h
        out (8),a
        ld a,16
        out (8),a
        xor a
        ld (key),a
        ld (prefix),a
        ld (column),a
        ld hl,0f800h
        ld (cursor),hl
        ld (hl),32
        ld de,0f801h
        ld bc,1919
        ldir
        jp home
unavailable: xor a
        ret
const:  ld a,(key)
        or a
        jr nz,keyready
        in a,(0eh)
        and 1
        ret z
        in a,(0ch)
        cp 0e0h
        jr nz,keychar
        ld a,1
        ld (prefix),a
        xor a
        ret
keychar: ld b,a
        ld a,(prefix)
        or a
        ret z
        xor a
        ld (prefix),a
        ld a,b
        and 7fh
        ld (key),a
        or a
        ret z
keyready: ld a,0ffh
        ret
conin:  call const
        or a
        jr z,conin
        ld a,(key)
        push af
        xor a
        ld (key),a
        pop af
        ret
conout: push af
        push bc
        push de
        push hl
        ld a,c
        cp 13
        jr z,cr
        cp 10
        jr z,lf
        cp 8
        jr z,bs
        cp 9
        jr z,tab
        cp 12
        jr z,clear
        cp 32
        jr c,coutdone
        ld hl,(cursor)
        ld (hl),a
        inc hl
        ld (cursor),hl
        ld a,(column)
        inc a
        cp 80
        jr c,colstore
        xor a
colstore: ld (column),a
        call scroll
        jr coutdone
cr:     ld a,(column)
        ld e,a
        ld d,0
        ld hl,(cursor)
        or a
        sbc hl,de
        ld (cursor),hl
        xor a
        ld (column),a
        jr coutdone
lf:     ld hl,(cursor)
        ld de,80
        add hl,de
        ld (cursor),hl
        call scroll
        jr coutdone
bs:     ld a,(column)
        or a
        jr z,coutdone
        dec a
        ld (column),a
        ld hl,(cursor)
        dec hl
        ld (cursor),hl
        jr coutdone
tab:    ld c,32
        call conout
        ld a,(column)
        and 7
        jr nz,tab
        jr coutdone
clear:  ld hl,0f800h
        ld (cursor),hl
        xor a
        ld (column),a
        ld (hl),32
        ld de,0f801h
        ld bc,1919
        ldir
coutdone: pop hl
        pop de
        pop bc
        pop af
        ret
scroll: ld hl,(cursor)
        ld de,0ff80h
        or a
        sbc hl,de
        ret c
        ld hl,0f850h
        ld de,0f800h
        ld bc,1840
        ldir
        ld hl,0ff30h
        ld (hl),32
        ld de,0ff31h
        ld bc,79
        ldir
        ld hl,(cursor)
        ld de,80
        or a
        sbc hl,de
        ld (cursor),hl
        ret
seldsk: ld a,c
        ld (drive),a
        ld hl,0
        or a
        ret nz
        inc hl
        ret
settrk: ld (track),bc
        ret
setsec: ld (record),bc
        ret
setdma: ld (dma),bc
        ret
sectrn: ld h,b
        ld l,c
        inc hl
        ret
home:   xor a
        ld (valid),a
        ld b,81
homelp: in a,(6)
        bit 7,a
        jr z,homed
        push bc
        ld a,09fh
        call step
        pop bc
        djnz homelp
        ld a,1
        ret
homed:  xor a
        ld (cylinder),a
        ld hl,0
        ld (track),hl
        ret
step:   out (4),a
        and 7fh
        out (4),a
        or 80h
        out (4),a
        ld bc,600
stepwait: dec bc
        ld a,b
        or c
        jr nz,stepwait
        ret
position:
        ld a,(drive)
        or a
        jp nz,error
        in a,(6)
        and 1
        jp nz,error
        ld hl,(track)
        ld a,h
        or a
        jp nz,error
        ld a,l
        cp 160
        jp nc,error
        and 1
        ld (head),a
        srl l
        ld a,(cylinder)
seekloop: cp l
        jr z,seekdone
        push hl
        ld a,0bfh
        jr c,seekin
        ld a,09fh
        call step
        ld a,(cylinder)
        dec a
        jr seeksaved
seekin: call step
        ld a,(cylinder)
        inc a
seeksaved: ld (cylinder),a
        pop hl
        jr seekloop
seekdone: ld hl,(record)
        ld a,h
        or a
        jp nz,error
        ld a,l
        or a
        jp z,error
        cp 41
        jp nc,error
        dec a
        ld b,a
        and 7
        ld (subrecord),a
        ld a,b
        srl a
        srl a
        srl a
        inc a
        ld (sector),a
        xor a
        ret
; Fetch a complete field first, CRC offline. /WAIT provides byte pacing.
field:  ld hl,buffer
        ld bc,0302h
        ld de,4000
        ld a,(head)
        or a
        ld a,0a5h
        jr z,fieldstop
        ld a,0a1h
fieldstop: out (4),a
        and 0dfh
        out (4),a
markwait: in a,(6)
        and 2
        jr nz,markready
        dec de
        ld a,d
        or e
        jr nz,markwait
        jp errorstop
markready: inir
        in a,(c)
        ld (hl),a
        inc hl
        cp 0feh
        jr z,idfield
        cp 0fbh
        jr nz,errorstop
        ld a,(idonly)
        or a
        jr nz,errorstop
        ld b,0
        inir
        inir
        inir
        inir
        ld b,2
        inir
        ld de,1030
        jr fieldend
idfield: ld b,6
        inir
        ld de,10
fieldend: ld a,(head)
        or a
        ld a,0a5h
        jr z,stopnow
        ld a,0a1h
stopnow: out (4),a
        ld hl,buffer
        ld bc,0ffffh
        call crc
        ld a,b
        or c
        ret
errorstop: ld a,0a5h
        out (4),a
error:  ld a,1
        ret
; CRC CCITT, HL source, DE length, BC accumulator. Stream already stopped.
crc:    ld a,(hl)
        xor b
        ld b,a
        push de
        ld e,8
crcbit: sla c
        rl b
        jr nc,crcnox
        ld a,b
        xor 10h
        ld b,a
        ld a,c
        xor 21h
        ld c,a
crcnox: dec e
        jr nz,crcbit
        pop de
        inc hl
        dec de
        ld a,d
        or e
        jr nz,crc
        ret
findid: ld a,1
        ld (idonly),a
        ld a,24
        ld (attempts),a
findnext: call field
        or a
        jr nz,findretry
        ld a,(buffer+3)
        cp 0feh
        jr nz,findretry
        ld a,(cylinder)
        ld hl,buffer+4
        cp (hl)
        jr nz,findretry
        inc hl
        ld a,(head)
        cp (hl)
        jr nz,findretry
        inc hl
        ld a,(sector)
        cp (hl)
        jr nz,findretry
        inc hl
        ld a,3
        cp (hl)
        jr nz,findretry
        xor a
        ret
findretry: ld a,(attempts)
        dec a
        ld (attempts),a
        jr nz,findnext
        jp error
readsector: ld a,(valid)
        or a
        jr z,cachemiss
        ld a,(track)
        ld hl,cachedtrack
        cp (hl)
        jr nz,cachemiss
        ld a,(sector)
        inc hl
        cp (hl)
        jr nz,cachemiss
        xor a
        ret
cachemiss: xor a
        ld (valid),a
        call findid
        or a
        ret nz
        xor a
        ld (idonly),a
        call field
        or a
        ret nz
        ld a,(buffer+3)
        cp 0fbh
        jp nz,error
        ld a,(track)
        ld (cachedtrack),a
        ld a,(sector)
        ld (cachedsector),a
        ld a,1
        ld (valid),a
        xor a
        ret
read:   call position
        or a
        ret nz
        call readsector
        or a
        ret nz
        call recordptr
        ld de,(dma)
        ld bc,128
        ldir
        xor a
        ret
recordptr: ld a,(subrecord)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,buffer+4
        add hl,de
        ret
write:  call position
        or a
        ret nz
        in a,(6)
        and 20h
        jp z,error
        call readsector
        or a
        ret nz
        call recordptr
        ex de,hl
        ld hl,(dma)
        ld bc,128
        ldir
        ld hl,buffer
        ld bc,0ffffh
        ld de,1028
        call crc
        ld (hl),b
        inc hl
        ld (hl),c
        ; findid uses buffer, so preserve the prepared output separately.
        ld hl,buffer
        ld de,writebuf
        ld bc,1030
        ldir
        xor a
        ld (valid),a
        call findid
        or a
        ret nz
        ld a,(head)
        or a
        ld a,084h
        jr z,writegate
        ld a,080h
writegate: out (4),a
        ld hl,writebuf
        ld bc,0000h
        otir
        otir
        otir
        otir
        ld b,8
        otir
        ld a,0a5h
        out (4),a
        ld hl,writebuf
        ld de,buffer
        ld bc,1030
        ldir
        ld a,1
        ld (valid),a
        xor a
        ret
; Bootstrap scans the user-0 directory for the single-extent CPM3.SYS.
; GENCPM's reverse 128-byte record order is retained on disk.
loader: di
        ld sp,0f700h
        call init
        ld bc,0
        call seldsk
        ld bc,4
        call settrk
        ld bc,1
        call setsec
        ld bc,dirrecord
        call setdma
        ld a,32
        ld (dirleft),a
scanrecord: call read
        or a
        jp nz,booterror
        ld hl,dirrecord
        ld b,4
scanentry: push bc
        push hl
        ld a,(hl)
        or a
        jr nz,nomatch
        inc hl
        ld de,sysname
        ld b,11
matchname: ld a,(hl)
        and 7fh
        ld c,a
        ld a,(de)
        cp c
        jr nz,nomatch
        inc hl
        inc de
        djnz matchname
        ld a,(hl)
        or a
        jr nz,nomatch
        pop hl
        pop bc
        ld de,sysentry
        ld bc,32
        ldir
        jp loadsys
nomatch: pop hl
        ld de,32
        add hl,de
        pop bc
        djnz scanentry
        ld hl,(record)
        inc hl
        ld (record),hl
        ld a,(dirleft)
        dec a
        ld (dirleft),a
        jr nz,scanrecord
        jp booterror
loadsys: ld a,(sysentry+14)
        or a
        jp nz,booterror
        ; Exactly five blocks contain the 72-record generated system.
        ; Validate all before reading any payload into resident memory.
        ld ix,sysentry+16
        ld b,5
sysblocks: ld l,(ix+0)
        ld h,(ix+1)
        ld de,2
        or a
        sbc hl,de
        jp c,booterror
        ld de,388
        or a
        sbc hl,de
        jp nc,booterror
        ld hl,sysentry+16
        ld a,5
        sub b
        ld c,a
        jr z,sysblocknext
sysunique: ld a,(hl)
        cp (ix+0)
        inc hl
        jr nz,sysdifferent
        ld a,(hl)
        cp (ix+1)
        jp z,booterror
sysdifferent: inc hl
        dec c
        jr nz,sysunique
sysblocknext: inc ix
        inc ix
        djnz sysblocks
        ld b,6
sysunused: ld a,(ix+0)
        or a
        jp nz,booterror
        inc ix
        djnz sysunused
        ld a,(sysentry+15)
        cp 72
        jp nz,booterror
        xor a
        ld (filerec),a
        call sysread
        or a
        jp nz,booterror
        ld hl,dirrecord
        ld de,sysheader
        ld b,6
checkheader: ld a,(de)
        cp (hl)
        jp nz,booterror
        inc hl
        inc de
        djnz checkheader
        ld a,2
        ld (filerec),a
        ld hl,0bf80h
        ld (destination),hl
sysloop: call sysread
        or a
        jp nz,booterror
        ld hl,dirrecord
        ld de,(destination)
        ld bc,128
        ldir
        ld hl,(destination)
        ld de,128
        or a
        sbc hl,de
        ld (destination),hl
        ld a,(filerec)
        inc a
        ld (filerec),a
        cp 72
        jr nz,sysloop
        ld hl,09d00h
        ld de,2300h
        ld bc,0ffffh
        call crc
        ld hl,system_crc
        or a
        sbc hl,bc
        jp nz,booterror
        jp 0bc00h
sysread: ld a,(filerec)
        srl a
        srl a
        srl a
        srl a
        add a,a
        ld l,a
        ld h,0
        ld de,sysentry+16
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,d
        cp 2
        jp nc,error
        ex de,hl
        ld a,h
        or l
        jp z,error
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(filerec)
        and 15
        ld e,a
        ld d,0
        add hl,de
        ld de,160
        add hl,de
        ld bc,0
        ld de,40
sysdivide: or a
        sbc hl,de
        jr c,sysdivdone
        inc bc
        jr sysdivide
sysdivdone: add hl,de
        inc hl
        ld (record),hl
        ld (track),bc
        ld bc,dirrecord
        call setdma
        jp read
booterror: ld hl,bootmsg
bootprint: ld a,(hl)
        or a
        jr z,boothalt
        ld c,a
        call conout
        inc hl
        jr bootprint
boothalt: di
        halt
        jr boothalt
sysname: db 'CPM3    SYS'
sysheader: db 0c0h,23h,0,0,0,0bch
bootmsg: db 'CP/M 3 boot error: CPM3.SYS',13,10,0
idonly: db 0
valid: db 0
cachedtrack: db 0
cachedsector: db 0
cursor: dw 0f800h
column: db 0
key: db 0
prefix: db 0
drive: db 0
track: dw 0
record: dw 1
dma: dw 80h
cylinder: db 0
head: db 0
sector: db 1
subrecord: db 0
attempts: db 0
dirleft: db 0
filerec: db 0
destination: dw 0
sysentry: ds 32
dirrecord: ds 128
buffer: ds 1032
writebuf: ds 1032
platform_end:
        end
