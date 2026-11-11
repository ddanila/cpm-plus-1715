"""Managed session safety checks; no physical serial devices."""
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import tempfile
import unittest
from argparse import Namespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from cpm_session import EscapeFilter, snapshot, status, config_at, clean_disk
from serial_session import lock_session


class ManagedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.config = dict(schema=1, kind='managed-robotron1715', platform_sha256='platform',
                           image_sha256='source', requires_boot=False)
        (self.path/'identity.json').write_text(json.dumps(self.config))
        (self.path/'disk.img').write_bytes(bytes(819200))

    def action(self, command, name='saved'):
        return snapshot(Namespace(command=command, name=name), self.path)

    def test_snapshot_restore_preserves_rollback_and_requires_boot(self):
        self.action('snapshot')
        changed = b'x'*819200
        (self.path/'disk.img').write_bytes(changed)
        self.action('restore')
        self.assertEqual((self.path/'disk.img').read_bytes(), bytes(819200))
        self.assertTrue(config_at(self.path)['requires_boot'])
        self.assertEqual(next((self.path/'snapshots').glob('rollback-*/disk.img')).read_bytes(), changed)
        with self.assertRaises(FileExistsError): self.action('snapshot')

    def test_active_session_blocks_media_changes(self):
        with lock_session(self.path/'session.lock'):
            with self.assertRaises(BlockingIOError): self.action('snapshot')
            with self.assertRaises(BlockingIOError): self.action('restore')

    def test_journal_blocks_snapshot(self):
        (self.path/'disk.img.jhj').write_bytes(b'uncertain')
        with self.assertRaisesRegex(ValueError, 'journal'): self.action('snapshot')
        self.assertTrue((self.path/'disk.img.jhj').exists())

    def test_corrupted_snapshot_does_not_replace_disk(self):
        self.action('snapshot')
        (self.path/'snapshots/saved/disk.img').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'integrity'): self.action('restore')
        self.assertEqual((self.path/'disk.img').read_bytes(), bytes(819200))

    def test_snapshot_identity_mismatch(self):
        self.action('snapshot')
        meta = self.path/'snapshots/saved/identity.json'
        value = json.loads(meta.read_text()); value['platform_sha256']='other'
        meta.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'compatibility'): self.action('restore')

    def test_invalid_names(self):
        for name in ('../bad', '', 'a/b'):
            with self.assertRaises(ValueError): self.action('snapshot', name)

    def test_stale_pid_does_not_claim_live_service(self):
        (self.path/'status.json').write_text(json.dumps(dict(state='running', pid=os.getpid())))
        self.assertEqual(status(self.path)['state'], 'failed')
        self.assertFalse(status(self.path)['live'])

    def test_legacy_session_is_rejected(self):
        (self.path/'identity.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'legacy'): config_at(self.path)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux prctl parent-death contract")
    def test_native_host_guard_exits_on_parent_death(self):
        pidfile = self.path/'pid'
        program = "import os,time; from pathlib import Path; Path("+repr(str(pidfile))+").write_text(str(os.getpid())); time.sleep(30)"
        parent_program = ("import os,subprocess,time; subprocess.Popen(["+repr(sys.executable)+", "+
            repr(str(ROOT/'tools/serial_host_guard.py'))+", str(os.getpid()), "+repr(sys.executable)+
            ", '-c', "+repr(program)+"]); time.sleep(30)")
        parent = subprocess.Popen([sys.executable, '-c', parent_program])
        try:
            until=time.monotonic()+5
            while not pidfile.exists() and time.monotonic()<until: time.sleep(.01)
            child=int(pidfile.read_text())
            parent.kill(); parent.wait(timeout=5)
            until=time.monotonic()+5
            while time.monotonic()<until:
                stat=Path(f'/proc/{child}/stat')
                if not stat.exists() or stat.read_text().split()[2]=='Z': break
                time.sleep(.01)
            else: self.fail('host survived supervisor death')
        finally:
            if parent.poll() is None: parent.kill(); parent.wait(timeout=5)

    def test_escape_across_chunks_and_literal(self):
        escape = EscapeFilter()
        self.assertEqual(escape.feed(b'a\x03\x1d'), (b'a\x03', False))
        self.assertEqual(escape.feed(b'\x1db'), (b'\x1db', False))
        self.assertEqual(escape.feed(b'\x1ddignored'), (b'', True))
        self.assertEqual(EscapeFilter().feed(b'\x1dx'), (b'\x1dx', False))


if __name__ == '__main__': unittest.main()
