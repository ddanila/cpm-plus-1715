#!/usr/bin/env python3
"""Emulator-only raster regression for both ordinary PC1715 platform builds."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def symbols(path):
    return {n: int(v, 16) for n, v in re.findall(
        r'^([a-zA-Z_][\w]*)\s+([0-9A-F]+)\s', path.read_text(), re.M)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dac', type=Path, default=ROOT.parent/'dac-emulation')
    p.add_argument('--out', type=Path, default=ROOT/'build/plain-video')
    p.add_argument('--before', type=Path, help='Optional old platform .cim/.lst directory: assert blank raster')
    a = p.parse_args(); dac = a.dac.resolve(); a.out.mkdir(parents=True, exist_ok=True)
    exe = a.out.resolve()/'probe'
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I', str(dac),
        str(ROOT/'tests/plain_video_probe.c'), str(dac/'machines/robotron1715/pc1715.c'),
        str(dac/'common/cpu/z80.c'), str(dac/'common/trace/trace.c'), '-o', str(exe)], check=True)
    results = []
    for directory, legacy in [(ROOT/'build', False)] + ([(a.before, True)] if a.before else []):
        for name, boundary in [('platform', 'home'), ('platform-serial', 'remote_init')]:
            syms = symbols(directory/(name+'.lst')); image = directory/(name+'.cim')
            args = [str(exe), str(image), f'{syms["init"]:x}', f'{syms[boundary]:x}',
                    f'{syms["localout"]:x}', str(int(legacy)), str(a.out/(name+('-before' if legacy else '')+'.ppm'))]
            result = subprocess.run(args, check=True, text=True, capture_output=True)
            row = json.loads(result.stdout); row.update(platform=name, sha256=hashlib.sha256(image.read_bytes()).hexdigest())
            results.append(row); print(row, flush=True)
    (a.out/'result.json').write_text(json.dumps({'hardware_executed': False, 'cases': results}, indent=2)+'\n')

if __name__ == '__main__': main()
