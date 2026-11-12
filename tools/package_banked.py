#!/usr/bin/env python3
"""SPDX-License-Identifier: MIT. Package banked W4 artifacts with current evidence."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import zipfile
from banked_contract import source_fingerprint, validate_banked

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ravi',type=Path,required=True)
    p.add_argument('--host',type=Path,required=True)
    p.add_argument('--reports',type=Path,nargs='+',required=True)
    p.add_argument('--reproducible',type=Path,required=True)
    a=p.parse_args()
    files={}
    for rate,suffix in [(9600,'9600'),(41600,'fast'),(62400,'62400')]:
        image=ROOT/f'out/cpm-plus-1715-wm-banked-{suffix}.img'
        platform=ROOT/f'build/banked/platform-{suffix}.cim'
        manifest=ROOT/f'build/banked/platform-{suffix}.json'
        validate_banked(image,platform,manifest,rate)
        for path in [image,platform,manifest,ROOT/f'out/cpm-plus-1715-wm-{suffix}.img',
                     ROOT/f'build/platform-wm-{suffix}.cim']:
            files[str(path.relative_to(ROOT))]=path
    for name in ['system-map.json','cpm3.sys']:
        files['build/banked/'+name]=ROOT/'build/banked'/name
    for name in ['serial_wm_w4.py','serial_wm.py','serial_session.py','banked_contract.py','media.py']:
        files['tools/'+name]=ROOT/'tools'/name
    files['jukuhost']=a.host
    rom=a.ravi/'src/ravi/backends/robotron1715w/rom-w4.bin'
    files['rom-w4.bin']=rom
    for name in ['LICENSE','NOTICE.md','docs/wm-banked.md','docs/wm-serial.md',
                 'tools/wm-dependencies.json','third_party/cpm3/LICENSE.md',
                 'third_party/JUKU-LICENSE','third_party/juku-common/LICENSE-BSD-2-Clause']:
        files[name]=ROOT/name
    rates=set(); faults=set(); cases=set(); fragmented=False
    fingerprint=source_fingerprint(ROOT)
    reproducible=json.loads(a.reproducible.read_text())
    if not reproducible['complete'] or not reproducible['fresh_source_build'] or reproducible['source_sha256']!=fingerprint:
        raise ValueError('fresh reproducibility evidence required')
    for name,expected in reproducible['equal_outputs'].items():
        if digest(ROOT/name)!=expected: raise ValueError('stale reproducibility evidence')
    files['reports/reproducible.json']=a.reproducible
    subprocess.run([str(ROOT/'build/banked-probe'),str(ROOT/'build/banked/cpm3.sys')],check=True)
    for i,path in enumerate(a.reports):
        r=json.loads(path.read_text())
        if not r['complete'] or r['hardware_executed'] or r['profile']!='banked':
            raise ValueError('requires completed banked emulator evidence')
        if r['source_sha256']!=fingerprint or r['probe_sha256']!=digest(ROOT/'build/wm-probe'):
            raise ValueError('stale source/probe evidence')
        suffix={9600:'9600',41600:'fast',62400:'62400'}[r['baud']]
        for key,file in [('image_sha256',ROOT/f'out/cpm-plus-1715-wm-banked-{suffix}.img'),
            ('platform_sha256',ROOT/f'build/banked/platform-{suffix}.cim'),
            ('rom_sha256',rom),('host_sha256',a.host)]:
            if r[key]!=digest(file): raise ValueError('stale artifact: '+key)
        cases.update(r['cases'])
        if r['fault']: faults.add(r['fault'])
        else:
            rates.add(r['baud']); fragmented |= r['fragmented']
        files[f'reports/{i}.json']=path
    required={'advertised TPA verified','RAM disk full directory, full disk, random records and reuse',
              '80 KiB cross-bank roundtrip','cold boot clears RAM disk','SUBMIT and SHOW',
              'read-only media unchanged','corrupt disk CRC recovered'}
    if rates!={9600,41600,62400} or not fragmented or not required<=cases or faults!={'header','payload','duplicate','foreign','missing-bank'}:
        raise ValueError('incomplete banked acceptance coverage')
    manifest=dict(version='wm-banked-1',hardware_qualified=False,source_sha256=fingerprint,
                  files={name:digest(path) for name,path in files.items()})
    output=ROOT/'out/cpm-plus-1715-wm-banked.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,path in sorted(files.items()):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o100755 if name=='jukuhost' else 0o100644)<<16
            archive.writestr(info,path.read_bytes())
        archive.writestr(zipfile.ZipInfo('manifest.json',(1980,1,1,0,0,0)),json.dumps(manifest,indent=2)+'\n')
    print(output)

if __name__=='__main__': main()
