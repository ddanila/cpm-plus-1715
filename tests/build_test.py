# SPDX-License-Identifier: MIT
import binascii, importlib.util, json, re, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from check_runtime import files
class BuildTests(unittest.TestCase):
 def test_sys_and_map(self):
  d=(ROOT/'build/cpm3.sys').read_bytes();self.assertEqual(d[:6],bytes.fromhex('c023000000bc'));self.assertEqual(len(d),9216)
  m=json.loads((ROOT/'build/system-map.json').read_text())
  self.assertEqual(m['system_crc'],binascii.crc_hqx(b''.join(d[i:i+128] for i in range(len(d)-128,255,-128)),65535))
  s=(ROOT/'build/platform.lst').read_text();end=int(re.search(r'^platform_end\s+([0-9A-F]+)\s',s,re.M)[1],16)
  self.assertLess(end,0xf600) # leave >=256 bytes for stack below F700
 def test_rom_descriptor(self):
  d=(ROOT/'out/cpm-plus-1715.img').read_bytes();self.assertEqual(len(d),819200)
  self.assertEqual(d[:6],bytes.fromhex('03f000000100'))
  self.assertEqual(int.from_bytes(d[9:11],'little'),0x4000)
  self.assertEqual(int.from_bytes(d[12:14],'little'),0x4000)
  count=int.from_bytes(d[14:16],'little');self.assertLessEqual(128+count*128,20480)
  self.assertEqual(d[16],255)
  for i in [100,108,116]:self.assertEqual(d[i:i+8],bytes([80,5,3,27,3,1,1,0]))
 def test_directory(self):
  d=(ROOT/'out/cpm-plus-1715.img').read_bytes();f=files(d)
  self.assertEqual(f[b'CPM3    SYS'],(ROOT/'build/cpm3.sys').read_bytes())
  self.assertTrue(f[b'HELLO   TXT'].startswith(b'Native CP/M Plus'))
  used={0,1}
  for off in range(20480,24576,32):
   e=d[off:off+32]
   if e[0]==229:continue
   self.assertEqual(e[0],0)
   for j in range(16,32,2):
    b=int.from_bytes(e[j:j+2],'little')
    if not b:continue
    self.assertNotIn(b,used);self.assertLess(b,390);used.add(b)
if __name__=='__main__':unittest.main()
