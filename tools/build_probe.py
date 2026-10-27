#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import argparse,subprocess,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--pico',type=Path,default=Path('../Pico1715'));p.add_argument('--dac',type=Path,default=Path('../dac-emulation'));p.add_argument('--firmware',action='store_true');a=p.parse_args()
r=Path(__file__).resolve().parents[1];pico=a.pico.resolve();dac=a.dac.resolve()
for name,path in [('pico',pico),('dac',dac)]:
 expected=json.loads((r/'dependencies.json').read_text())[name]
 actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
 if actual!=expected:raise RuntimeError(f'{name} revision {actual} != {expected}')
 subprocess.run(['git','-C',str(path),'diff','--quiet'],check=True)
 subprocess.run(['git','-C',str(path),'diff','--cached','--quiet'],check=True)
if a.firmware:
 subprocess.run(['python3',str(pico/'tools/build_cosim.py'),'--dac',str(dac),'--out',str(r/'build/firmware'),'--firmware'],check=True)
else:
 sources=[pico/'tools/classic_probe.c',pico/'model/controller.c',dac/'machines/robotron1715/pc1715.c',dac/'common/cpu/z80.c',dac/'common/trace/trace.c']
 subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(dac),*map(str,sources),'-o',str(r/'build/classic-probe')],check=True)
