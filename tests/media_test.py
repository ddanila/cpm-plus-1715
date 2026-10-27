# SPDX-License-Identifier: MIT
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from media import add, inspect, DIRECTORY, BLOCK, SIZE

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.base = (ROOT / 'out/cpm-plus-1715.img').read_bytes()

    def test_roundtrip_users_attributes_extents_and_padding(self):
        data = bytes(range(256)) * 2300 + b'end'
        image = add(self.base, 'large.bin', data, user=15, attributes='RSA')
        f = inspect(image)[15, 'LARGE.BIN']
        self.assertGreater(len(f.slots), 32)  # exercise S2, not just EX
        self.assertEqual(f.data[:len(data)], data)
        self.assertEqual(f.data[len(data):], b'\xe5' * (-len(data) % 128))
        self.assertEqual(f.attributes, 'RSA')
        self.assertEqual(image[:DIRECTORY], self.base[:DIRECTORY])
        for key, old in inspect(self.base).items():
            self.assertEqual(inspect(image)[key], old)

    def test_empty_and_replace(self):
        image = add(self.base, 'EMPTY', b'')
        self.assertEqual(inspect(image)[0, 'EMPTY'].data, b'')
        with self.assertRaises(ValueError): add(image, 'EMPTY', b'x')
        image = add(image, 'EMPTY', b'x', replace=True)
        self.assertEqual(inspect(image)[0, 'EMPTY'].data, b'x' + b'\xe5' * 127)

    def test_rejections(self):
        for name in ('../X', 'TOOLONGGG.TXT', '*.TXT', 'A.B.C', 'CPM3.SYS', 'CCP.COM'):
            with self.subTest(name=name), self.assertRaises(ValueError): add(self.base, name, b'x')
        for off, val in ((DIRECTORY+15, 129), (DIRECTORY+16, 1),
                         (DIRECTORY+18, 2), (DIRECTORY+14, 1)):
            broken = bytearray(self.base); broken[off] = val
            with self.subTest(off=off), self.assertRaises(ValueError): inspect(broken)
        with self.assertRaises(ValueError): inspect(self.base[:-1])

    def test_capacity_is_transactional(self):
        original = bytearray(self.base)
        with self.assertRaisesRegex(ValueError, 'disk full'): add(original, 'BIG', bytes(SIZE))
        self.assertEqual(original, self.base)
        image = self.base
        count = 128 - sum(len(f.slots) for f in inspect(image).values())
        for i in range(count): image = add(image, f'E{i}', b'')
        with self.assertRaisesRegex(ValueError, 'directory full'): add(image, 'MORE', b'')
        self.assertEqual(len(inspect(image)), 128)

    def test_cli_exclusive_output_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            image, data, output = (Path(tmp)/n for n in ('disk.img','file','out.img'))
            image.write_bytes(self.base); data.write_bytes(b'abc')
            cmd = [sys.executable, str(ROOT/'tools/disk_image.py'), 'add', str(image), 'NEW.TXT', str(data), '--output']
            self.assertNotEqual(subprocess.run(cmd+[str(image)],capture_output=True).returncode, 0)
            self.assertEqual(image.read_bytes(), self.base)
            self.assertEqual(subprocess.run(cmd+[str(output)],capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(cmd+[str(output)],capture_output=True).returncode, 0)

    def test_builder_matches_previous_allocation_algorithm(self):
        # Independent allocation oracle, including the new diagnostic utility.
        # Boot bytes intentionally change with platform code.
        import zipfile
        from build_image import put
        d = bytearray([0xe5])*SIZE; block=2
        items=[('CPM3.SYS',(ROOT/'build/cpm3.sys').read_bytes()),('CCP.COM',(ROOT/'third_party/cpm3/ccp.com').read_bytes())]
        with zipfile.ZipFile(ROOT/'third_party/cpm3/releases/cpm3bin_unix-20260607.zip') as z:
            items += [(n.upper()+'.COM',z.read(n+'.com')) for n in ('dir','type','pip','erase','rename','show','set','submit')]
        items += [('P1715TST.COM',(ROOT/'build/p1715test.cim').read_bytes())]
        items += [('HELLO.TXT',b'Native CP/M Plus on Robotron 1715\r\n\x1a'),('TEST.SUB',b'DIR HELLO.TXT\r\nTYPE HELLO.TXT\r\n\x1a')]
        for slot,(name,data) in enumerate(items):
            stem,ext=name.split('.');e=bytearray(32);e[1:12]=(stem.ljust(8)+ext.ljust(3)).encode();e[15]=(len(data)+127)//128
            for j in range((len(data)+2047)//2048):
                e[16+j*2:18+j*2]=block.to_bytes(2,'little');part=data[j*2048:(j+1)*2048];off=DIRECTORY+block*BLOCK;d[off:off+len(part)]=part;block+=1
            d[DIRECTORY+slot*32:DIRECTORY+(slot+1)*32]=e
        self.assertEqual(self.base[DIRECTORY:],d[DIRECTORY:])
