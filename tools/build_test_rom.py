#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source-built CI entry fixture, NOT a Robotron ROM replacement.
Runs ordinary Z80 instructions to install our platform services and enter their
filesystem loader. Does not test the historical ROM descriptor or 4000h stage.
"""
from pathlib import Path
import struct
root=Path(__file__).resolve().parents[1]
payload=(root/'build/platform.cim').read_bytes()
# Copy the ROM overlay to underlying RAM, then the platform to C000h.
code=bytearray.fromhex('f331003f210000110000010008edb0')
source=15+3+3+3+2+2+2+3
code+=bytes([0x21])+struct.pack('<H',source)+bytes.fromhex('1100c001')+struct.pack('<H',len(payload))+bytes.fromhex('edb03e00d328c333c0')
assert len(code)==source
assert len(code)+len(payload)<=2048
(root/'build/test.rom').write_bytes(bytes(code)+payload+bytes(2048-len(code)-len(payload)))
