#!/usr/bin/env python3
"""MIT: bind the RAM/video diagnostic guard to the built banked platform."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
data = (root / 'build/banked/platform-62400.cim').read_bytes()[:32]
assert len(data) == 32
(root / 'build/video-signature.inc').write_text(
    '; Generated from the current 62400 platform jump table.\n' +
    '\n'.join('        db ' + ','.join(f'0{x:02x}h' for x in data[i:i+8])
              for i in range(0, 32, 8)) + '\n')
