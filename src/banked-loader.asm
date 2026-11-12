; MIT. Bounded two-extent SYS loader; all code/state remains in common RAM.
loader: di
        ld sp,0f700h
        call init
        ; Test that each selector has private low RAM and shared upper RAM.
        ; Scratch at 0080h is overwritten by CP/M initialization.
        ld b,4
bprobe_write:
        ld a,b
        rlca
        rlca
        rlca
        rlca
        or b
        out (24h),a
        ld a,b
        ld (0080h),a
        djnz bprobe_write
        ld b,4
bprobe_read:
        ld a,b
        rlca
        rlca
        rlca
        rlca
        or b
        out (24h),a
        ld a,(0080h)
        cp b
        jp nz,booterror
        djnz bprobe_read
        ld a,11h
        out (24h),a
        ld hl,bblocks
        ld de,bblocks+1
        ld bc,bsys_blocks*2
        ld (hl),0
        ldir
        xor a
        ld (bextent_seen),a
        ld (bpass),a
bscan_start:
        ld hl,4
        ld (track),hl
        ld hl,1
        ld (record),hl
        ld a,32
        ld (dirleft),a
bscan_record:
        ld bc,dirrecord
        call setdma
        call read
        or a
        jp nz,booterror
        ld ix,dirrecord
        ld b,4
bscan_entry:
        push bc
        ld a,(ix+0)
        cp 0e5h
        jp z,bscan_next
        or a
        jr nz,bother
        push ix
        pop hl
        inc hl
        ld de,sysname
        ld b,11
bmatch: ld a,(hl)
        and 7fh
        ld c,a
        ld a,(de)
        cp c
        jr nz,bother
        inc hl
        inc de
        djnz bmatch
        ld a,(bpass)
        or a
        jp nz,bscan_next
        ld a,(ix+14)
        or a
        jp nz,booterror
        ld a,(ix+12)
        cp 2
        jp nc,booterror
        or a
        ld c,1
        ld de,bblocks
        ld b,128
        jr z,bextent
        ld c,2
        ld de,bblocks+16
        ld b,bsys_records-128
bextent:
        ld a,(bextent_seen)
        and c
        jp nz,booterror
        ld a,(bextent_seen)
        or c
        ld (bextent_seen),a
        ld a,(ix+15)
        cp b
        jp nz,booterror
        push ix
        pop hl
        ld bc,16
        add hl,bc
        ; First extent: 8 blocks. Last extent: remaining blocks, then zeros.
        ld a,(ix+12)
        or a
        ld bc,16
        jr z,bcopy_blocks
        ld bc,(bsys_blocks-8)*2
bcopy_blocks:
        ldir
        ld a,(ix+12)
        or a
        jp z,bscan_next
        ld b,(16-bsys_blocks)*2
bzero_tail:
        ld a,(hl)
        or a
        jp nz,booterror
        inc hl
        djnz bzero_tail
        jp bscan_next
bother:
        ld a,(bpass)
        or a
        jp z,bscan_next
        ; Reject any other active directory entry claiming a SYS block.
        push ix
        pop hl
        ld de,16
        add hl,de
        ld b,8
bowner:
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        push hl
        push bc
        ld hl,bblocks
        ld b,bsys_blocks
bowner_cmp:
        ld a,(hl)
        inc hl
        cp e
        jr nz,bowner_skip
        ld a,(hl)
        cp d
        jp z,booterror
bowner_skip:
        inc hl
        djnz bowner_cmp
        pop bc
        pop hl
        djnz bowner
bscan_next:
        ld de,32
        add ix,de
        pop bc
        dec b
        jp nz,bscan_entry
        ld hl,(record)
        inc hl
        ld (record),hl
        ld a,(dirleft)
        dec a
        ld (dirleft),a
        jp nz,bscan_record
        ld a,(bpass)
        or a
        jp nz,bload
        ld a,(bextent_seen)
        cp 3
        jp nz,booterror
        ; Validate SYS blocks and duplicates before loading either segment.
        ld ix,bblocks
        ld b,bsys_blocks
bvalidate:
        ld l,(ix+0)
        ld h,(ix+1)
        ld de,2
        or a
        sbc hl,de
        jp c,booterror
        ld de,388
        or a
        sbc hl,de
        jp nc,booterror
        ld hl,bblocks
        ld a,bsys_blocks
        sub b
        ld c,a
        jr z,bvalid_next
bduplicate:
        ld a,(hl)
        inc hl
        cp (ix+0)
        jr nz,bdup_next
        ld a,(hl)
        cp (ix+1)
        jp z,booterror
bdup_next:
        inc hl
        dec c
        jr nz,bduplicate
bvalid_next:
        inc ix
        inc ix
        djnz bvalidate
        ld a,1
        ld (bpass),a
        jp bscan_start
bload: xor a
        ld (filerec),a
        call bsysread
        or a
        jp nz,booterror
        ld hl,dirrecord
        ld de,bheader
        ld b,6
bheader_check:
        ld a,(de)
        cp (hl)
        jp nz,booterror
        inc de
        inc hl
        djnz bheader_check
        ld a,2
        ld (filerec),a
        ld hl,0df80h
        ld (destination),hl
        ld a,bsys_common_records
        call bsegment
        ld hl,0bf80h
        ld (destination),hl
        ld a,bsys_bank_records
        call bsegment
        ld hl,0c000h
        ld de,2000h
        ld bc,0ffffh
        call crc
        ld hl,bsys_common_crc
        or a
        sbc hl,bc
        jp nz,booterror
        ld hl,bsys_bank_start
        ld de,bsys_bank_records*128
        ld bc,0ffffh
        call crc
        ld hl,bsys_bank_crc
        or a
        sbc hl,bc
        jp nz,booterror
        jp bsys_entry
bsegment:
        ld (bremaining),a
bsegment_loop:
        call bsysread
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
        ld a,(bremaining)
        dec a
        ld (bremaining),a
        jr nz,bsegment_loop
        ret
bsysread:
        ld a,(filerec)
        srl a
        srl a
        srl a
        srl a
        add a,a
        ld l,a
        ld h,0
        ld de,bblocks
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        ex de,hl
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
bdivide:
        or a
        sbc hl,de
        jr c,bdivdone
        inc bc
        jr bdivide
bdivdone:
        add hl,de
        inc hl
        ld (record),hl
        ld (track),bc
        ld bc,dirrecord
        call setdma
        jp read
bheader: db 0e0h,20h,0c0h,bsys_bank_records/2,0,0c6h
bremaining: db 0
bpass: db 0
bextent_seen: db 0
bblocks: ds bsys_blocks*2+1
