# SPDX-License-Identifier: MIT
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from keyboard_cases import pairs,fixture
from media import inspect
class KeyboardContracts(unittest.TestCase):
 def test_diagnostics_and_storage_bounds(self):
  m=json.loads((ROOT/'build/keyboard-map.json').read_text());s=m['symbols']
  self.assertEqual(m['capacity'],128)
  self.assertEqual(s['keyqueue']+128,s['platform_end'])
  self.assertLess(s['platform_end'],0xf600)
  self.assertTrue(all(0xc000<=v<0xf600 for v in s.values()))
 def test_workload_owns_scratch_and_result_blocks(self):
  base=(ROOT/'out/cpm-plus-1715.img').read_bytes();d=fixture(base,0,64);f=inspect(d)
  self.assertEqual(f[0,'KBDDATA.BIN'].blocks,tuple(range(380,388)))
  self.assertEqual(f[0,'KBDOUT.BIN'].blocks,(388,))
  for k,v in inspect(base).items():self.assertEqual(f[k].data,v.data)
 def test_schedule_cadence(self):
  self.assertEqual(pairs(b'AB',start=7),[(7,224),(1007,65),(101007,224),(102007,66)])
