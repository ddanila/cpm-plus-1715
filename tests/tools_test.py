"""Exact byte lengths and offline tool upgrades, without serial hardware."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from media import add, inspect, DIRECTORY
from tool_bundle import bundle, install
from session_tools import install_tools, retain_inputs
from cpm_session import snapshot, config_at
from serial_session import lock_session


class ExactTests(unittest.TestCase):
    def test_used_bytes_at_record_and_extent_boundaries(self):
        base = bytes([0xe5])*819200
        for n in (0,1,127,128,129,16383,16384,16385,49153):
            data = bytes(i % 256 for i in range(n))
            disk = add(base, 'DATA.BIN', data, exact=True)
            f = inspect(disk)[(0,'DATA.BIN')]
            self.assertEqual(f.exact_data, data)
            self.assertEqual(len(f.data), ((n+127)//128)*128)
            for slot in f.slots:
                self.assertEqual(disk[slot+13], n%128)
            legacy = inspect(add(base,'DATA.BIN',data))[(0,'DATA.BIN')]
            self.assertEqual(legacy.exact_data, legacy.data)


@unittest.skipUnless((ROOT/'out/tools/manifest.json').exists(), 'make tools first')
class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.session = Path(self.temp.name)
        image = ROOT/'out/cpm-plus-1715-serial-base.img'
        platform = ROOT/'build/platform-serial.cim'
        self.config = dict(schema=1,kind='managed-robotron1715',image=str(image),platform=str(platform),
                           image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                           platform_sha256=hashlib.sha256(platform.read_bytes()).hexdigest(),requires_boot=False,read_only=False)
        (self.session/'identity.json').write_text(json.dumps(self.config))
        self.original = add(image.read_bytes(),'USER.BIN',b'\0\x1a\xff\n',exact=True,user=3)
        (self.session/'disk.img').write_bytes(self.original)

    def test_upgrade_idempotence_snapshot_and_rollback(self):
        snapshot(Namespace(command='snapshot',name='before'),self.session)
        install_tools(self.session)
        installed=(self.session/'disk.img').read_bytes()
        entries=inspect(installed)
        self.assertEqual(entries[(3,'USER.BIN')].exact_data,b'\0\x1a\xff\n')
        self.assertTrue(config_at(self.session)['requires_boot'])
        self.assertEqual(len(config_at(self.session)['tools']['files']),13)
        self.assertIn('/inputs/', config_at(self.session)['image'])
        install_tools(self.session)
        self.assertEqual((self.session/'disk.img').read_bytes(),installed)
        snapshot(Namespace(command='restore',name='before'),self.session)
        self.assertEqual((self.session/'disk.img').read_bytes(),self.original)
        self.assertNotIn('tools',config_at(self.session))
        self.assertTrue(config_at(self.session)['requires_boot'])

    def test_conflict_leaves_disk_and_configuration_untouched(self):
        conflicting=add(self.original,'CAT.COM',b'user program',exact=True)
        (self.session/'disk.img').write_bytes(conflicting)
        with self.assertRaisesRegex(ValueError,'unrecognized'): install_tools(self.session)
        self.assertEqual((self.session/'disk.img').read_bytes(),conflicting)
        self.assertEqual(config_at(self.session),self.config)

    def test_live_journal_and_readonly_rejected(self):
        with lock_session(self.session/'session.lock'):
            with self.assertRaises(BlockingIOError): install_tools(self.session)
        (self.session/'disk.img.jhj').write_bytes(b'pending')
        with self.assertRaisesRegex(ValueError,'journal'): install_tools(self.session)
        (self.session/'disk.img.jhj').unlink()
        self.config['read_only']=True
        (self.session/'identity.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'read-only'): install_tools(self.session)
        self.assertEqual((self.session/'disk.img').read_bytes(),self.original)

    def test_write_failure_rolls_back(self):
        from session_tools import replace_disk
        calls=[]
        def fail_once(session,data):
            calls.append(1)
            if len(calls)==1: raise OSError('injected failure')
            return replace_disk(session,data)
        with patch('session_tools.replace_disk',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'injected'): install_tools(self.session)
        self.assertEqual((self.session/'disk.img').read_bytes(),self.original)
        self.assertFalse((self.session/'tools-transaction.json').exists())
        self.assertNotIn('tools',config_at(self.session))

    def test_unavailable_legacy_input_rejected(self):
        self.config['image_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'legacy image unavailable'):
            retain_inputs(self.config,self.session)

    def test_interrupted_transaction_requires_restore(self):
        from cpm_session import validate_config
        snapshot(Namespace(command='snapshot',name='safe'),self.session)
        (self.session/'tools-transaction.json').write_text('{"rollback":"safe"}')
        with self.assertRaisesRegex(ValueError,'interrupted'):
            validate_config(config_at(self.session),self.session)
        with self.assertRaisesRegex(ValueError,'interrupted'): install_tools(self.session)
        snapshot(Namespace(command='restore',name='safe'),self.session)
        self.assertFalse((self.session/'tools-transaction.json').exists())
        self.assertEqual((self.session/'disk.img').read_bytes(),self.original)

    def test_retained_input_survives_source_replacement(self):
        copied=self.session/'original.img';copied.write_bytes(Path(self.config['image']).read_bytes())
        config=dict(self.config,image=str(copied))
        pinned=retain_inputs(config,self.session)
        copied.write_bytes(b'rebuilt elsewhere')
        self.assertEqual(hashlib.sha256(Path(pinned['image']).read_bytes()).hexdigest(),config['image_sha256'])
        self.assertEqual(retain_inputs(pinned,self.session),pinned)

    def test_full_directory_preflight(self):
        image=self.original
        for i in range(128):
            try: image=add(image,f'F{i}.TXT',b'')
            except ValueError: break
        before=image
        with self.assertRaisesRegex(ValueError,'directory full'): install(image)
        self.assertEqual(image,before)
