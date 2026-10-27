#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build from source in a fresh temporary tree and compare generated outputs."""
from pathlib import Path
import shutil,subprocess,tempfile,hashlib,json
from evidence import sources, outputs, OUTPUTS, atomic_json
r=Path(__file__).resolve().parents[1]
before=sources()
with tempfile.TemporaryDirectory(prefix='cpm1715-repro-') as temp:
 d=Path(temp)
 for name in ['src','tools','tests','third_party']:shutil.copytree(r/name,d/name,ignore=shutil.ignore_patterns('__pycache__'))
 shutil.copy2(r/'Makefile',d/'Makefile')
 shutil.copy2(r/'dependencies.json',d/'dependencies.json')
 subprocess.run(['make','-j2','all','test'],cwd=d,check=True)
 names=OUTPUTS
 hashes={}
 for name in names:
  assert (r/name).read_bytes()==(d/name).read_bytes(),name
  hashes[name]=hashlib.sha256((d/name).read_bytes()).hexdigest()
 assert sources()==before, 'sources changed during reproducibility check'
 atomic_json(r/'reports/reproducible.json', {'schema':2,'status':'passed','source_sha256':before,'dependencies':json.loads((r/'dependencies.json').read_text()),'fresh_source_build':True,'equal_outputs':hashes})
 print('PASS fresh source build matches',len(names),'outputs')
