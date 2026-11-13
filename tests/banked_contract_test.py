"""Banked artifact mismatch checks; no hardware access."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from banked_contract import validate_banked
ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/'build/banked/platform-62400.json').exists(), 'make wm-banked first')
class BankedContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d=Path(self.tmp.name)
        self.image=d/'disk.img'; self.platform=d/'platform.cim'; self.manifest=d/'manifest.json'
        for target, source in [(self.image,'out/cpm-plus-1715-wm-banked-62400.img'),
            (self.platform,'build/banked/platform-62400.cim'),
            (self.manifest,'build/banked/platform-62400.json')]:
            target.write_bytes((ROOT/source).read_bytes())
    def validate(self, rate=62400):
        return validate_banked(self.image,self.platform,self.manifest,rate)
    def test_valid_and_wrong_rate(self):
        contract,_=self.validate()
        self.assertEqual(contract['common_base'],0xc000)
        with self.assertRaises(ValueError): self.validate(9600)
    def test_modified_disk(self):
        data=bytearray(self.image.read_bytes()); data[-1]^=1; self.image.write_bytes(data)
        with self.assertRaises(ValueError): self.validate()
    def test_modified_platform(self):
        data=bytearray(self.platform.read_bytes()); data[100]^=1; self.platform.write_bytes(data)
        with self.assertRaises(ValueError): self.validate()
    def test_profile_and_entry(self):
        data=json.loads(self.manifest.read_text()); data['platform_entry']=0xc033
        self.manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.validate()

try:
    import serial_wm_w4
except ModuleNotFoundError as exc:
    if exc.name != 'ravi': raise
    serial_wm_w4 = None

@unittest.skipUnless(serial_wm_w4 is not None and (ROOT/'build/banked/platform-62400.json').exists(),
                     'pinned Ravi and banked artifacts required')
class W4DefaultTests(unittest.TestCase):
    def test_default_and_explicit_fallback_are_distinct_sessions(self):
        from unittest.mock import patch
        for fallback in [False,True]:
            with self.subTest(nonbanked=fallback), tempfile.TemporaryDirectory() as directory:
                if fallback and not (ROOT/'build/platform-wm-62400.cim').exists():
                    self.skipTest('make wm-62400 for fallback launcher coverage')
                session=Path(directory)/'session'
                args=['serial_wm_w4.py','boot','--serial','/dev/test',
                      '--session',str(session),'--console-pty','/dev/test-console',
                      '--host',str(ROOT/'build/banked/cpm3.sys')]
                if fallback: args += ['--nonbanked']
                with patch.object(sys,'argv',args), patch.object(serial_wm_w4,'SerialTransport',
                        side_effect=RuntimeError('stop before hardware')) as port:
                    with self.assertRaisesRegex(RuntimeError,'stop before hardware'):
                        serial_wm_w4.main()
                    port.assert_called_once()
                identity=json.loads((session/'identity.json').read_text())
                self.assertEqual(identity.get('profile'),None if fallback else '1715m-banked')
                self.assertEqual((session/'disk.img').stat().st_size,819200)
                self.assertEqual((session/'disk-b.img').exists(),not fallback)
                if not fallback:
                    self.assertEqual((session/'disk-b.img').read_bytes(),bytes([0xe5])*819200)
                    self.assertEqual(identity['drive_map'],
                        ['serial-a','serial-b','floppy-0','floppy-1','ram'])


    def test_invalid_b_image_rejected_before_port_open(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'bad.img'; image.write_bytes(b'bad')
            args=['serial_wm_w4.py','boot','--serial','/dev/test',
                  '--session',str(Path(directory)/'session'),'--console-pty','/dev/test-console',
                  '--host',str(ROOT/'build/banked/cpm3.sys'),'--drive-b',str(image)]
            with patch.object(sys,'argv',args), patch.object(serial_wm_w4,'SerialTransport') as port:
                with self.assertRaises(ValueError): serial_wm_w4.main()
                port.assert_not_called()
