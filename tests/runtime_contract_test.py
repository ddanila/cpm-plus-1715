# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from pattern_workload import fixture,nearly_full
class AllocationTests(unittest.TestCase):
 def test_full_fixture_has_ten_blocks(self):
  d=nearly_full(fixture((ROOT/'out/cpm-plus-1715.img').read_bytes(),256,expect_full=True),10);used={0,1}
  for at in range(20480,24576,32):
   e=d[at:at+32]
   if e[0]<16:used.update(int.from_bytes(e[j:j+2],'little') for j in range(16,32,2))
  self.assertEqual(len(set(range(390))-used),10)
if __name__=='__main__':unittest.main()
