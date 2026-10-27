#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build from source in a fresh temporary tree and compare generated outputs."""
from pathlib import Path
import shutil,subprocess,tempfile,hashlib,json
r=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='cpm1715-repro-') as temp:
 d=Path(temp)
 for name in ['src','tools','tests','third_party']:shutil.copytree(r/name,d/name,ignore=shutil.ignore_patterns('__pycache__'))
 shutil.copy2(r/'Makefile',d/'Makefile')
 subprocess.run(['make','-j2','all','test'],cwd=d,check=True)
 outputs=['build/cpm3.sys','build/platform.cim','build/test.rom','out/cpm-plus-1715.img','build/system-map.json']
 hashes={}
 for name in outputs:
  assert (r/name).read_bytes()==(d/name).read_bytes(),name
  hashes[name]=hashlib.sha256((d/name).read_bytes()).hexdigest()
 (r/'reports/reproducible.json').write_text(json.dumps({'schema':1,'fresh_source_build':True,'equal_outputs':hashes},indent=2)+'\n')
 print('PASS fresh source build matches',len(outputs),'outputs')
