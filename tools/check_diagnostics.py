#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run portable guest diagnostics and verify disk contents independently."""
import argparse, hashlib, json, os
from pathlib import Path
from check_runtime import execute
from media import inspect, add
p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--image',type=Path,default=Path('out/cpm-plus-1715.img'));p.add_argument('--out',type=Path,required=True);p.add_argument('--extended',action='store_true');p.add_argument('--backend',choices=['native','firmware'],required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
base=a.image.read_bytes();program=Path('build/p1715test.cim').read_bytes()
if (0,'P1715TST.COM') not in inspect(base):base=add(base,'P1715TST.COM',program)
else:assert inspect(base)[(0,'P1715TST.COM')].data[:len(program)]==program
original={key:f.data for key,f in inspect(base).items()}
env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')};env.update(PICO1715_TIMED='0',PICO1715_KEY_START='30000000',PICO1715_CYCLES='400000000')
results=[]
def run(name,data,cmd,marker,readonly=False):
 dest=a.out/name;dest.mkdir();source=dest/'input.img';source.write_bytes(data)
 code,stdout,stderr=execute([str(a.binary.resolve()),str(a.rom.resolve()),str(source.resolve()),str(dest.resolve()),cmd,*(['readonly'] if readonly else [])],env|{'PICO1715_STOP_TEXT':marker},dest)
 assert code==0,(name,code,stderr[-1000:])
 screen=(dest/'screen.txt').read_text();assert marker in screen,(name,code,screen[-1000:]);out=(dest/'disk.img').read_bytes()
 for key,before in original.items():assert inspect(out)[key].data==before,(name,'unrelated file changed',key)
 if readonly:assert data==out
 results.append({'case':name,'marker':marker,'exit_status':code,'input_sha256':hashlib.sha256(data).hexdigest(),'output_sha256':hashlib.sha256(out).hexdigest()})
 return out
run('info',base,'P1715TST I\r','P1715TEST INFO PASS')
written=run('write',base,'P1715TST W\r','P1715TEST WRITE PASS')
expected=b''.join(bytes(i^j for j in range(128)) for i in range(256));expected=b'P1715TEST-v1\0\1\2\3'+expected[16:]
assert inspect(written)[(0,'P1715TST.DAT')].data==expected
run('cold-verify',written,'P1715TST R\r','P1715TEST VERIFY PASS',True)
assert run('collision',written,'P1715TST W\r','P1715TEST COLLISION FAIL')==written
# Deliberate corruption of our scratch file only.
f=inspect(written)[(0,'P1715TST.DAT')];bad=bytearray(written);bad[20480+f.blocks[0]*2048+71]^=1
assert run('corrupt',bytes(bad),'P1715TST R\r','P1715TEST VERIFY FAIL',True)==bytes(bad)
if a.extended:
 from pattern_workload import nearly_full
 full=nearly_full(base,2)
 run('disk-full',full,'P1715TST W\r','P1715TEST IO FAIL')
 run('write-protect',base,'P1715TST W\r','CP/M Error On A: Disk I/O',True)
clean=run('cleanup',written,'P1715TST C\r','P1715TEST CLEAN PASS');assert (0,'P1715TST.DAT') not in inspect(clean)
run('cold-missing',clean,'P1715TST R\r','P1715TEST VERIFY FAIL',True)
report={'schema':1,'hardware_executed':False,'backend':a.backend,'runner_provenance':json.loads(Path(str(a.binary)+'.json').read_text()),'binary_sha256':hashlib.sha256(a.binary.read_bytes()).hexdigest(),'rom_sha256':hashlib.sha256(a.rom.read_bytes()).hexdigest(),'program_sha256':hashlib.sha256(program).hexdigest(),'cases':results}
(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('diagnostics PASS',a.backend,len(results))
