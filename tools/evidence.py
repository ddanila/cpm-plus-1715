# SPDX-License-Identifier: MIT
"""Shared qualification identities and atomic report publication."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ['build/cpm3.sys', 'build/platform.cim', 'build/test.rom',
           'out/cpm-plus-1715.img', 'build/system-map.json',
           'build/reliability-test.cim', 'build/directory-test.cim',
           'build/keyboard-map.json', 'build/keyboard-test.cim', 'build/p1715test.cim']

def sha(data):
    return hashlib.sha256(data).hexdigest()

def sources():
    paths = [ROOT/'Makefile', ROOT/'dependencies.json', ROOT/'third_party/inputs.json']
    paths += [p for folder in ('src', 'tools', 'tests', 'third_party') for p in (ROOT/folder).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(paths)}

def outputs():
    return {p: sha((ROOT/p).read_bytes()) for p in OUTPUTS}

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)
