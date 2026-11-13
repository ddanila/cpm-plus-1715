#!/usr/bin/env python3
"""Build the banked 1715M system from pinned DRI tools. SPDX-License-Identifier: MIT."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import pexpect
import regenerate_cpm3 as dri

ROOT = dri.ROOT

def build(out=None):
    out = out or ROOT / 'build/banked'
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='1715m-banked-') as temporary:
        work = Path(temporary)
        dri.extract_tools(work)  # verifies both release archive hashes
        with zipfile.ZipFile(dri.ARCHIVES['binary'][0]) as archive:
            for name in ('resbdos3.spr', 'bnkbdos3.spr'):
                (work/name).write_bytes(archive.read(name))
        shutil.copyfile(dri.INPUTS/'gencpm.dat', work/'gencpm.dat')
        subprocess.run([str(ROOT/'build/bin/zmac'), '--zmac', '-o', str(out/'floppy.cim'), str(ROOT/'src/wm-floppy.asm')], cwd=ROOT, check=True)
        floppy = (out/'floppy.cim').read_bytes()
        if len(floppy)>0xc00: raise ValueError('floppy code overlaps common buffer')
        include = '        ds 0a00h-($-boot$entry)\n' + ''.join('        db '+','.join(f'0{x:02x}h' for x in floppy[i:i+16])+'\n' for i in range(0,len(floppy),16))
        bios = (ROOT/'src/cpm3-banked-bios.asm').read_text().replace('; FLOPPY_DRIVER',include)
        (work/'jbios.asm').write_bytes(bios.replace('\n','\r\n').encode())
        dri.dos_text(dri.INPUTS/'scb.asm', work/'scb.asm')
        for args in [('RMAC.COM','jbios'), ('RMAC.COM','scb'),
                     ('LINK.COM','bnkbios3[b]=jbios,scb')]:
            dri.run([str(dri.DEFAULT_ZXCC), *args], work)
        child = pexpect.spawn(str(dri.DEFAULT_ZXCC), ['GENCPM.COM'],
                              cwd=str(work), encoding='latin1', timeout=15)
        transcript = ''
        for prompt, answer in [('Use GENCPM.DAT','Y'), ('Create a new','N'),
                ('Display Load Map',''), ('console columns',''),
                ('lines in console',''), ('Backspace',''), ('Rubout',''),
                ('default drive',''), ('Top page','DF'), ('Bank switched','Y'),
                ('Common memory','C0'), ('Long error','Y'), ('Accept new','Y')]:
            child.expect(prompt)
            transcript += child.before + child.after
            child.sendline(answer)
        child.expect(pexpect.EOF)
        transcript += child.before
        child.close()
        if child.exitstatus != 0:
            raise RuntimeError(transcript)
        system = (work/'cpm3.sys').read_bytes()
        for name in ('jbios.prn', 'bnkbios3.sym'):
            if (work/name).exists(): shutil.copyfile(work/name, out/name)
    top, pages, bank_top, bank_pages = system[:4]
    entry = int.from_bytes(system[4:6], 'little')
    if (top, pages, bank_top, entry) != (0xe0, 0x20, 0xc0, 0xc600):
        raise ValueError('unexpected banked common layout')
    if len(system) != 256 + (pages + bank_pages)*256 or not 128 < len(system)//128 < 240:
        raise ValueError('unsupported system size')
    def segment(offset, count, end, bank):
        payload = system[offset:offset+count*256]
        memory = b''.join(payload[i:i+128] for i in range(len(payload)-128,-1,-128))
        return dict(bank=bank, start=end-count*256, top=end,
                    records=count*2, crc=binascii.crc_hqx(memory,65535))
    segments = [segment(256,pages,top*256,0),
                segment(256+pages*256,bank_pages,bank_top*256,0)]
    contract = dict(profile='1715m-banked', platform_start=0xe000,
        platform_entry=0xe033, platform_limit=0xf600, stack_top=0xf700,
        bios_entry=entry, common_base=0xc000, segments=segments,
        sys_records=len(system)//128, sys_sha256=hashlib.sha256(system).hexdigest())
    (out/'cpm3.sys').write_bytes(system)
    (out/'system-map.json').write_text(json.dumps(contract,indent=2)+'\n')
    (out/'gencpm.log').write_text(transcript)
    values = dict(bsys_records=len(system)//128, bsys_blocks=(len(system)+2047)//2048,
        bsys_entry=entry, bsys_common_records=pages*2,
        bsys_bank_records=bank_pages*2, bsys_bank_start=segments[1]['start'],
        bsys_common_crc=segments[0]['crc'], bsys_bank_crc=segments[1]['crc'])
    (out/'system.inc').write_text(''.join(f'{k} equ {v}\n' for k,v in values.items()))
    print(transcript)
    return contract

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix='1715m-repro-') as directory:
            rebuilt = Path(directory)
            build(rebuilt)
            for name in ('cpm3.sys','system-map.json','system.inc'):
                if (rebuilt/name).read_bytes() != (ROOT/'build/banked'/name).read_bytes():
                    raise ValueError('banked regeneration mismatch: '+name)
        print('BANKED-REPRODUCIBLE: PASS')
    else:
        build()
