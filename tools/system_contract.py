#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
from pathlib import Path
import binascii,json,hashlib
root=Path(__file__).resolve().parents[1]
s=(root/'build/cpm3.sys').read_bytes()
assert s[:6]==bytes.fromhex('c023000000bc') and len(s)==9216
memory=b''.join(s[i:i+128] for i in range(len(s)-128,255,-128))
crc=binascii.crc_hqx(memory,65535)
(root/'build/system.inc').write_text(f'system_crc equ {crc}\n')
(root/'build/system-map.json').write_text(json.dumps(dict(system_start=0x9d00,bios_entry=0xbc00,system_top=0xc000,platform_start=0xc000,platform_limit=0xf700,stack_top=0xf700,screen_start=0xf800,system_crc=crc,sys_sha256=hashlib.sha256(s).hexdigest()),indent=2)+'\n')
