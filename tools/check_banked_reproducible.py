#!/usr/bin/env python3
"""SPDX-License-Identifier: MIT. Fresh source/tool build of all banked artifacts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from banked_contract import source_fingerprint
ROOT=Path(__file__).resolve().parents[1]

def main():
    fingerprint=source_fingerprint(ROOT)
    names=['build/banked/'+n for n in ['cpm3.sys','system.inc','system-map.json']]
    for suffix in ['9600','fast','62400']:
        names += [f'build/banked/platform-{suffix}.{ext}' for ext in ['cim','json']]
        names += [f'out/cpm-plus-1715-wm-banked-{suffix}.img']
    with tempfile.TemporaryDirectory(prefix='1715m-fresh-') as directory:
        fresh=Path(directory)
        for name in ['src','tools','third_party']:
            shutil.copytree(ROOT/name,fresh/name,ignore=shutil.ignore_patterns('.git','__pycache__'))
        shutil.copyfile(ROOT/'Makefile',fresh/'Makefile')
        subprocess.run(['make','-j2','wm-banked'],cwd=fresh,check=True)
        hashes={}
        for name in names:
            original=(ROOT/name).read_bytes()
            if original!=(fresh/name).read_bytes(): raise ValueError('not reproducible: '+name)
            hashes[name]=hashlib.sha256(original).hexdigest()
    if fingerprint!=source_fingerprint(ROOT): raise ValueError('source changed during build')
    report=ROOT/'reports/banked-reproducible.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(dict(complete=True,fresh_source_build=True,
        source_sha256=fingerprint,equal_outputs=hashes),indent=2)+'\n')
    print('BANKED FRESH BUILD: PASS',report)

if __name__=='__main__': main()
