# SPDX-License-Identifier: MIT
import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from media import inspect
class DiagnosticsPackageTests(unittest.TestCase):
 def test_source_built_utility_is_in_image(self):
  code=(ROOT/'build/p1715test.cim').read_bytes();file=inspect((ROOT/'out/cpm-plus-1715.img').read_bytes())[(0,'P1715TST.COM')]
  self.assertEqual(file.data[:len(code)],code)
  self.assertIn(b'P1715TEST WRITE PASS',code);self.assertIn(b'P1715TEST COLLISION FAIL',code)
