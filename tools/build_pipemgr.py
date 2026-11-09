"""Reproduce pinned PIPEMGR code/relocations, then apply the local stage reset fix."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def flatten(source, origin):
    # PMA cseg/dseg concatenation. zmac treats dot labels as local, and packs
    # two-character constants in the opposite order; normalize those explicitly.
    parts = {'cseg': [], 'dseg': []}; segment = 'cseg'
    for line in source.splitlines(True):
        op = line.strip().lower()
        if op in parts: segment = op
        elif op not in ('end', '.z80'): parts[segment].append(line)
    source = ''.join(parts['cseg'])+''.join(parts['dseg'])
    source = re.sub(r'\.(dr|ud|ex|s1|s2|cr|rc|r0|r1|r2|\?\?)(?![\w?])',
                    lambda m: 'fcb_'+m[1].replace('??','extra'), source)
    source = source.replace("ld\thl,'NI'", 'ld\thl,04e49h')
    return f' org {origin:04x}h\n'+source


def assemble(source, work, label):
    versions = []
    for origin in (0x100, 0x200):
        stem = work/f'{label}-{origin:x}'
        stem.with_suffix('.asm').write_text(flatten(source, origin))
        subprocess.run([str(ROOT/'build/bin/zmac'), '--zmac', '-o', str(stem.with_suffix('.cim')),
                        str(stem.with_suffix('.asm'))], check=True, capture_output=True)
        # zmac omits the initial six uninitialized serial-number bytes.
        versions.append(bytes(6)+stem.with_suffix('.cim').read_bytes())
    code, relocated = versions
    if len(code) != len(relocated): raise ValueError('relocation changes code size')
    bitmap = bytearray((len(code)+7)//8)
    for i, (a,b) in enumerate(zip(code, relocated)):
        if a != b:
            if b != (a+1)&255: raise ValueError('non-page relocation at '+str(i))
            bitmap[i//8] |= 128 >> (i%8)
    return code, bytes(bitmap)


def build(work):
    source = (ROOT/'third_party/hitech/pipemgr/PIPEMGR.Z80').read_text()
    original = (ROOT/'third_party/hitech/pipemgr/PIPEMGR.RSX').read_bytes()
    code, bitmap = assemble(source, work, 'pm-original')
    if (len(code) != int.from_bytes(original[1:3],'little') or
            code+bitmap != original[256:256+len(code)+len(bitmap)]):
        raise ValueError('PIPEMGR source does not reproduce pinned binary and relocation bitmap')
    patch = '\tld\t(pclosed),a\t;Pipe file does not need opening\n'
    if source.count(patch) != 1: raise ValueError('PIPEMGR patch context changed')
    source = source.replace(patch, patch+'''\t; Robotron: each stage parses its own output redirectors. The upstream
\t; CloseOut no longer clears these after the direct-output rewrite.
\tld\t(outflg),a
\tld\t(errflg),a
\tld\t(oapp),a
''')
    # Fail closed on creation/open errors and on data/metadata write errors.
    source = source.replace('ecreat:\n', 'ecreat:\n\tjp\tboxioerror\n')
    source = source.replace('noinp:\n', 'noinp:\n\tjp\tboxioerror\n')
    for function in ('WRITESEQ', 'CLOSEF', 'SETATTR'):
        old = '\tld\tc,'+function+'\n\tcall\tfcbdos'
        check = '\n\tor\ta\n\tjp\tnz,boxioerror' if function == 'WRITESEQ' else '\n\tinc\ta\n\tjp\tz,boxioerror'
        source = source.replace(old, old+check)
    source = source.replace('initrsx:\n', 'initrsx:\n')
    # Set error mode after signature validation, before parsing redirects.
    old = '\tld\t(awake),a\n\txor\ta\n\tld\t(pclosed),a'
    new = '\tld\t(awake),a\n\tpush\tde\n\tld\tc,ERRMODE\n\tld\te,0feh\n\tcall\tfdos\n\tpop\tde\n\txor\ta\n\tld\t(pclosed),a'
    if old not in source: raise ValueError('PIPEMGR error mode patch context changed')
    source = source.replace(old, new)
    source = source.replace('killrsx:\n', 'killrsx:\n\tcall\tCloseOut\n\tcall\tCloseIn\n\tcall\tboxcleanup\n')
    source = source.replace('xferpipe:\n', 'xferpipe:\n\tcall\tboxchecknext\n')
    source += (ROOT/'src/cpmbox/pipemgr-error.inc').read_text()
    code, bitmap = assemble(source, work, 'pm-fixed')
    header = bytearray(original[:256]); header[1:3] = len(code).to_bytes(2,'little')
    result = bytes(header)+code+bitmap
    result += bytes((-len(result))%128)
    (work/'pipemgr.rsx').write_bytes(result)
