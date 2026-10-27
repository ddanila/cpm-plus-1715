#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind a prebuilt Node/WASM probe to the same runtime qualification harness."""
import argparse,json,shutil,subprocess
from pathlib import Path
from evidence import ROOT,sha,atomic_json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--pico',type=Path,default=ROOT.parent/'Pico1715')
p.add_argument('--node',default='node');p.add_argument('--firmware',action='store_true');a=p.parse_args()
pico=a.pico.resolve();deps=json.loads((ROOT/'dependencies.json').read_text());manifest=json.loads((pico/'build/browser/manifest.json').read_text())
assert not manifest['dirty'] and manifest['pico']==deps['pico'] and manifest['dac']==deps['dac'],'stale WASM build'
kind='firmware' if a.firmware else 'model';backend='firmware' if a.firmware else 'native'
node=shutil.which(a.node);assert node,'Node executable missing'
assets={str(pico/f'build/browser/{kind}/probe.{suffix}'):sha((pico/f'build/browser/{kind}/probe.{suffix}').read_bytes()) for suffix in ('cjs','wasm')}
probe=pico/f'build/browser/{kind}/probe.cjs'
binary=ROOT/f'build/wasm-{kind}-probe'
binary.write_text('#!/usr/bin/env python3\nimport hashlib,os,sys\nfrom pathlib import Path\nassets='+repr(assets)+'\nfor name,digest in assets.items():\n if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise SystemExit("WASM probe changed")\nos.execv('+repr(node)+','+repr([node,str(probe)])+'+sys.argv[1:])\n')
binary.chmod(0o755)
atomic_json(str(binary)+'.json',dict(schema=1,execution='wasm',backend=backend,binary_sha256=sha(binary.read_bytes()),dependencies=deps,assets=assets,compiler=manifest['compiler']))
print(binary)
