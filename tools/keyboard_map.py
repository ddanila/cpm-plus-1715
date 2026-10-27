#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export resident keyboard diagnostics without hardcoding private addresses."""
import json,re
from pathlib import Path
r=Path(__file__).resolve().parents[1]
listing=(r/'build/platform.lst').read_text()
names=('keyservice','keyhold','keyhead','keytail','keycount','keydrops','keydecoded','keycalls','prefix','keyqueue','platform_end')
symbols={n:int(re.search(r'^'+n+r'\s+([0-9A-F]+)\s',listing,re.M)[1],16) for n in names}
assert symbols['platform_end']<0xf600
(r/'build/keyboard-map.json').write_text(json.dumps(dict(schema=1,capacity=128,counter_bits=16,symbols=symbols),indent=2)+'\n')
(r/'build/keyboard.inc').write_text(''.join(f'{n} equ {v}\n' for n,v in symbols.items()))
