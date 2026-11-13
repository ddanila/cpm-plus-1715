        title   '1715M banked CP/M Plus 3.1 BIOS'

; Copyright (c) 2026 Danila Sukharev
; Developed with OpenAI GPT-5.6 Sol assistance.
; BSD-2-Clause; see ../LICENSE.
;
; Banked BIOS: common code at C600h, private data below C000h in bank 0.
; The serial adapter occupies E000h..F5FFh. CP/M banks 0/1 map to selectors
; 1/2; selectors 3/4 exclusively back the volatile E: disk.

true            equ     0ffffh
jmpop           equ     0c3h
bdos            equ     0005h
ccp             equ     0100h
default$fcb     equ     005ch
adapter         equ     0e000h
native$services equ     0
network$9600    equ     0

; CP/M 2-compatible adapter vectors.
a$boot          equ     adapter+0
a$wboot         equ     adapter+3
a$const         equ     adapter+6
a$conin         equ     adapter+9
a$conout        equ     adapter+12
a$list          equ     adapter+15
a$auxout        equ     adapter+18
a$auxin         equ     adapter+21
a$home          equ     adapter+24
a$seldsk        equ     adapter+27
a$settrk        equ     adapter+30
a$setsec        equ     adapter+33
a$setdma        equ     adapter+36
a$read          equ     adapter+39
a$write         equ     adapter+42
a$listst        equ     adapter+45
a$sectrn        equ     adapter+48

        cseg
        extrn @mxtpa
boot$entry: jmp boot
        jmp wboot
        jmp a$const
        jmp a$conin
        jmp a$conout
        jmp a$list
        jmp a$auxout
        jmp a$auxin
        jmp a$home
        jmp seldsk
        jmp settrk
        jmp setsec
        jmp setdma
        jmp read
        jmp write
        jmp a$listst
        jmp a$sectrn
        jmp ready
        jmp ready
        jmp ready
        jmp devtbl
        jmp return
        jmp drvtbl
        jmp return
        jmp success
        jmp move
        jmp return
        jmp selmem
        jmp setbnk
        jmp xmove
        jmp wboot
        jmp wboot
warm$entry equ boot$entry+3
stack$top equ 0f700h
boot:   lxi sp,stack$top
        mvi a,1
        sta cold$start
        ; Cold boot only: format two 48K RAM-disk halves.
        mvi a,33h
        call format
        mvi a,44h
        call format
        xra a
        call selmem
        call 0d000h ; initialize U8272, physical writes locked
        lxi h,signon
        call print
        jmp load$ccp
format: out 24h
        lxi h,0
        lxi b,0c000h
format$loop:
        mvi m,0e5h
        inx h
        dcx b
        mov a,b
        ora c
        jnz format$loop
        ret
wboot:  lxi sp,stack$top
        xra a
        sta cold$start
load$ccp:
        mvi a,1
        call selmem
        call    adapter+54 ; hide queued input from BDOS break polling
        call    set$jumps
        lda cold$start
        ora a
        jz ccp$reset$done
        ; BOOT may be called without reloading SYS: discard the previous
        ; login/allocation state after formatting E:, unlike a warm boot.
        mvi c,13
        call bdos
        xra a
        sta cold$start
ccp$reset$done:
        ; A transient may leave BDOS function 44's multi-sector count above
        ; one.  This loader advances its DMA destination by exactly one
        ; 128-byte record after each sequential read, so restore that contract
        ; before fetching CCP.COM.  Without this reset a fast PIP copy can
        ; leave (for example) a count of four or twelve; the following reads
        ; then overlap CCP chunks and warm boot eventually executes corrupted
        ; low memory.
        mvi     e,1
        mvi     c,44
        call    bdos
        lxi     h,default$fcb
        mvi     b,36
clear$fcb:
        mvi     m,0
        inx     h
        dcr     b
        jnz     clear$fcb
        lxi     h,ccp$name
        lxi     d,default$fcb+1
        mvi     b,11
copy$name:
        mov     a,m
        stax    d
        inx     h
        inx     d
        dcr     b
        jnz     copy$name
        mvi     a,1
        sta     default$fcb
        lxi     d,default$fcb
        mvi     c,15
        call    bdos
        inr     a
        jz      ccp$error
        lxi     d,ccp
read$ccp:
        push    d
        mvi     c,26
        call    bdos
        lxi     d,default$fcb
        mvi     c,20
        call    bdos
        pop     d
        ora     a
        jnz     ccp$done
        lxi     h,128
        dad     d
        xchg
        jmp     read$ccp
ccp$done:
        cpi     1
        jnz     ccp$error
        jmp     ccp

ccp$error:
        lxi     d,ccp$msg
        mvi     c,9
        call    bdos
        mvi     c,1
        call    bdos
        jmp     wboot

set$jumps:
        mvi     a,jmpop
        sta     0000h
        sta     0005h
        lxi     h,warm$entry
        shld    0001h
        lhld    @mxtpa
        shld    0006h
        ret


; Bank numbers exposed to CP/M: 0=system, 1=application.
; All routines and state involved in changing mappings are common.
selmem: push psw
        sta current$bank
        inr a
        push b
        mov b,a
        rlc
        rlc
        rlc
        rlc
        ora b
        out 24h
        pop b
        pop psw
        ret
setbnk: sta dma$bank
        ret
xmove:  mov a,b
        inr a
        rlc
        rlc
        rlc
        rlc
        sta move$map
        mov a,c
        inr a
        push h
        lxi h,move$map
        ora m
        mov m,a
        pop h
        ret
move:   push psw
        lda move$map
        ora a
        jz move$loop$check
        out 24h
move$loop$check:
        mov a,b
        ora c
        jz move$done
move$loop:
        ; PC001's split read/write mapping transfers between banks with
        ; Z80 LDIR. A scalar LDAX/MOV loop writes the read bank on hardware.
        ; MOVE takes DE=source, HL=destination; LDIR uses the reverse pair.
        xchg
        db 0edh,0b0h            ; Z80 LDIR (RMAC uses 8080 mnemonics)
        xchg
move$done:
        xra a
        sta move$map
        lda current$bank
        call selmem
        pop psw
        ret
settrk: mov h,b
        mov l,c
        shld disk$track
        jmp a$settrk
setsec: mov h,b
        mov l,c
        shld disk$sector
        jmp a$setsec
setdma: mov h,b
        mov l,c
        shld disk$dma
        lda current$bank
        sta dma$bank
        ret
seldsk: lxi h,0
        mov a,c
        cpi 5
        rnc
        sta disk$drive
        cpi 2
        jnc local$select
        push b
        push d
        call a$seldsk
        pop d
        pop b
local$select:
        lda disk$drive
        add a
        mov e,a
        mvi d,0
        lxi h,dph$table
        dad d
        mov e,m
        inx h
        mov d,m
        xchg
        ret
read:   xra a
        sta disk$write
        jmp diskio
write:  mvi a,1
        sta disk$write
; All physical I/O uses a common buffer, including the RAM disk.
diskio: lda disk$write
        ora a
        jz disk$transfer
        call from$dma
disk$transfer:
        lda disk$drive
        cpi 4
        jz ramio
        cpi 2
        jnc physical$io
        lxi b,staging
        call a$setdma
        lda disk$write
        ora a
        jz host$read
        call a$write
        jmp io$done
host$read:
        call a$read
        jmp io$done
physical$io:
        mov c,a
        lhld disk$sector
        xchg
        lhld disk$track
        db 0ddh,21h ; LD IX,common staging
        dw staging
        lda disk$write
        ora a
        jnz physical$write
        call 0d003h
        jmp io$done
physical$write:
        call 0d006h
        jmp io$done
ramio:  lhld disk$track
        mov a,h
        ora a
        jnz failure
        mov a,l
        cpi 96
        jnc failure
        ; Eight 128-byte sectors per 1K track.
        lhld disk$sector
        mov a,h
        ora a
        jnz failure
        mov a,l
        dcr a
        cpi 8
        jnc failure
        mov e,a
        mvi d,0
        lhld disk$track
        dad h
        dad h
        dad h
        dad d
        ; Logical record 0..767 -> selector 3/4 and offset.
        mvi a,3
        mov b,a
        lxi d,384
        push h
        mov a,l
        sub e
        mov l,a
        mov a,h
        sbb d
        mov h,a
        jc ram$first
        pop d
        inr b
        jmp ram$address
ram$first:
        pop h
ram$address:
        dad h
        dad h
        dad h
        dad h
        dad h
        dad h
        dad h
        mov a,b
        rlc
        rlc
        rlc
        rlc
        ora b
        out 24h
        lda disk$write
        ora a
        lxi d,staging
        jnz ram$copy
        xchg
ram$copy:
        lxi b,128
        call move
        xra a
io$done:
        ora a
        rnz
        lda disk$write
        ora a
        jnz success
        call to$dma
success:xra a
return: ret
failure:mvi a,1
        ret
from$dma:
        lda dma$bank
        inr a
        ori 10h
        out 24h
        lhld disk$dma
        xchg
        lxi h,staging
        lxi b,128
        jmp move
to$dma:
        lda dma$bank
        inr a
        rlc
        rlc
        rlc
        rlc
        ori 1
        out 24h
        lhld disk$dma
        lxi d,staging
        lxi b,128
        jmp move
ready:  mvi a,0ffh
        ret
devtbl: lxi h,0ffffh
        ret
drvtbl: lxi h,0ffffh
        ret
print:  mov a,m
        ora a
        rz
        mov c,a
        push h
        call a$conout
        pop h
        inx h
        jmp print
signon: db 13,10,'CP/M Plus 3.1 - Robotron 1715M banked',13,10,0
ccp$name: db 'CCP     COM'
ccp$msg: db 13,10,'1715M BIOS cannot load CCP.COM$'
cold$start: db 0
current$bank: db 0
dma$bank: db 0
move$map: db 0
disk$drive: db 0
disk$write: db 0
disk$track: dw 0
disk$sector: dw 1
disk$dma: dw 80h
staging: ds 128
; Reserve common BIOS to place RESBDOS at C000h and cap the TPA.
; FLOPPY_DRIVER
        ds 1a00h-($-boot$entry)
        dseg
        dw write,read,return,return
        db 0,0
xdph0: dw trans,0,0,0,0,0,dpb0,csv0,alv0,dirhead0,0ffffh,0ffffh
        db 0
        dw write,read,return,return
        db 4,0
xdph4: dw trans4,0,0,0,0,0,dpb4,0,alv4,dirhead4,0ffffh,0ffffh
        db 0
dph$table: dw xdph0,xdph1,xdph2,xdph3,xdph4
        dw write,read,return,return
        db 1,0
xdph1: dw trans,0,0,0,0,0,dpb0,csv1,alv1,dirhead1,0ffffh,0ffffh
        db 0
        dw write,read,return,return
        db 2,0
xdph2: dw trans,0,0,0,0,0,dpb0,csv2,alv2,dirhead2,0ffffh,0ffffh
        db 0
        dw write,read,return,return
        db 3,0
xdph3: dw trans,0,0,0,0,0,dpb0,csv3,alv3,dirhead3,0ffffh,0ffffh
        db 0
trans4: db 1,2,3,4,5,6,7,8
trans: db 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
        db 21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40
; A: unchanged 800K host disk.
dpb0: dw 40
        db 4,15,0
        dw 389,127
        db 0c0h,0
        dw 32,4
        db 0,0
; E: 96 x 1K blocks, two directory blocks, 64 directory entries.
dpb4: dw 8
        db 3,7,0
        dw 95,63
        db 0c0h,0
        dw 0,0
        db 0,0
csv0: ds 32
alv0: ds 98
alv4: ds 24
dirhead0: dw bcb0
dirhead4: dw bcb4
bcb0: db 0ffh,0,0,0,0,0,0,0,0,0
        dw dirbuf0
        db 0,0,0
bcb4: db 0ffh,0,0,0,0,0,0,0,0,0
        dw dirbuf4
        db 0,0,0
dirbuf0: ds 128
dirbuf4: ds 128
csv1: ds 32
alv1: ds 98
dirhead1: dw bcb1
bcb1: db 0ffh,0,0,0,0,0,0,0,0,0
        dw dirbuf1
        db 0,0,0
dirbuf1: ds 128
csv2: ds 32
alv2: ds 98
dirhead2: dw bcb2
bcb2: db 0ffh,0,0,0,0,0,0,0,0,0
        dw dirbuf2
        db 0,0,0
dirbuf2: ds 128
csv3: ds 32
alv3: ds 98
dirhead3: dw bcb3
bcb3: db 0ffh,0,0,0,0,0,0,0,0,0
        dw dirbuf3
        db 0,0,0
dirbuf3: ds 128
        end
