#!/usr/bin/env python3
"""Build pinned cpmbox sources with HI-TECH C under ZXCC, then attach PIPEMGR."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
import io
import tarfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('cat', 'cal', 'cp', 'du', 'find', 'hexdump', 'ls', 'mv', 'untar')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build():
    for name, expected in json.loads((ROOT/'third_party/tools-inputs.json').read_text()).items():
        if sha((ROOT/name).read_bytes()) != expected:
            raise ValueError('changed tool input: '+name)
    work = ROOT/'build/tools'
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    for p in (ROOT/'third_party/hitech/dist').iterdir():
        if p.is_file(): shutil.copyfile(p, work/p.name.lower())
    for p in (ROOT/'third_party/cpmbox/upstream').iterdir():
        if p.suffix in ('.c', '.h'): (work/p.name).write_text(p.read_text())
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(ROOT/'src/cpmbox/hitech.patch')], cwd=work, check=True, stdout=subprocess.DEVNULL)
    for p in (ROOT/'src/cpmbox').iterdir():
        if p.suffix in ('.c', '.h'): shutil.copyfile(p, work/p.name)
    close_source = (ROOT/'third_party/hitech/cpm/CLOSE.C').read_text()
    close_source = close_source.replace('uchar       luid;', 'uchar       luid;\n    int rc = 0;')
    close_source = close_source.replace('        bdos(CPMCLS, fc);', '        rc = bdos(CPMCLS, fc);')
    close_source = close_source.replace('            bdos(CPMSATT, fc);',
        '            if ((bdos(CPMSATT, fc) & 255) == 255) rc = 255;')
    close_source = close_source.replace('    return 0;', '    return (rc & 255) == 255 ? -1 : 0;')
    (work/'close.c').write_text(close_source)
    signal_source = (ROOT/'third_party/hitech/cpm/SIGNAL.C').read_text()
    signal_source = signal_source.replace('char\tc;', 'char\tc;\n    static unsigned char ticks;\n    if (++ticks & 15) return;')
    signal_source = signal_source.replace('bdos(CPMDCIO,0xFF)', '((bios(2) & 255) ? bios(3) : 0)')
    (work/'signal.c').write_text(signal_source)
    from build_pipemgr import build as build_rsx
    build_rsx(work)
    with zipfile.ZipFile(ROOT/'third_party/cpm3/releases/cpm3bin_unix-20260607.zip') as z:
        for name in ('gencom', 'setdef'): (work/(name+'.com')).write_bytes(z.read(name+'.com'))
    def run(*args):
        p = subprocess.run([str(ROOT/'build/bin/zxcc'), *args], cwd=work, capture_output=True, timeout=120)
        output = p.stdout + p.stderr
        with (work/'build.log').open('ab') as log: log.write(output)
        if p.returncode or re.search(rb'undefined|bad int|fatal|can.t open|can.t find|multiply defined|error:', output, re.I):
            raise RuntimeError(output.decode(errors='replace'))
        return output
    subprocess.run([str(ROOT/'build/bin/zmac'), '--zmac', '-o', str(work/'tpa.cim'), str(ROOT/'src/cpmbox/tpa.asm')], check=True, capture_output=True)
    # Exercise the actual ported checksum code under the pinned compiler.
    # This catches its unsigned-char -> long compound-add code-generation bug.
    tar = io.BytesIO()
    with tarfile.open(fileobj=tar, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        member = tarfile.TarInfo('CHECK.BIN'); member.size = 1
        archive.addfile(member, io.BytesIO(b'x'))
    (work/'check.tar').write_bytes(tar.getvalue())
    source = (work/'untar.c').read_text()
    checksum = source[source.index('static long parse_octal'):source.index('static BOOL is_end_of_archive')]
    (work/'ctest.c').write_text('#include <stdio.h>\n#include <cpm.h>\n'
        'void pm_fail(char *s) { bdos(9,"COMPILER TEST FAILED$"); bdos(0,0); }\n'+checksum+
        'static char data[512];\nint main(void) { FILE *f=fopen("check.tar","rb");'
        'if (!f || fread(data,1,512,f)!=512 || !verify_checksum(data)) pm_fail("valid");'
        'data[0]^=1; if(verify_checksum(data)) pm_fail("invalid");'
        'bdos(9,"CHECKSUM PASS$"); return 0; }\n')
    run('c309.com', 'ctest.c')
    if b'CHECKSUM PASS' not in run('ctest.com'):
        raise RuntimeError('compiled tar checksum regression failed')
    run('c309.com', 'probe.c')
    run('gencom.com', 'probe', 'pipemgr')
    for name in NAMES:
        # Original frontend avoids -ERSX diagnostics: ZXCC has no resident PIPEMGR.
        support = {
            'cal': ['date.c'], 'mv': ['error.c'],
            'untar': ['error.c', 'bdos.c'],
        }.get(name, ['dirs.c', 'compat.c', 'error.c', 'term.c', 'bdos.c'])
        run('c309.com', name+'.c', 'getopt.c', 'port.c', 'close.c', 'signal.c', *support)
        target = work/(name+'.com')
        if not target.exists(): raise RuntimeError(name+' failed to compile; see build.log')
        raw = target.read_bytes()
        if len(raw) < 1024: raise RuntimeError(name+" suspiciously short compiler output")
        output = run('gencom.com', name, 'pipemgr')
        if b'GENCOM completed' not in output or target.stat().st_size <= len(raw):
            raise RuntimeError(name+' RSX attachment failed')
    destination = ROOT/'out/tools'
    destination.mkdir(parents=True, exist_ok=True)
    files = [n+'.com' for n in NAMES] + ['pipemgr.rsx', 'gencom.com', 'setdef.com']
    manifest = dict(schema=1, profile='robotron-serial-a', files={})
    for name in files:
        data = (work/name).read_bytes()
        (destination/name.upper()).write_bytes(data)
        manifest['files'][name.upper()] = dict(sha256=sha(data), size=len(data))
    data = (ROOT/'src/cpmbox/TOOLS.TXT').read_text().replace('\n', '\r\n').encode('ascii')+b'\x1a'
    (destination/'TOOLS.TXT').write_bytes(data)
    manifest['files']['TOOLS.TXT'] = dict(sha256=sha(data), size=len(data))
    (destination/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Built nine PIPEMGR-attached tools; manifest:', destination/'manifest.json')


if __name__ == '__main__': build()
