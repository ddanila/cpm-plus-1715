"""Faults at the bootstrap/console/ownership boundaries, without physical devices."""
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT.parent/'ravi/src'))
from serial_session import Console, HostService, bootstrap, positive
from check_serial_hardware import lock_session, main as hardware_main


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.left, self.right = socket.socketpair()
        self.addCleanup(self.left.close); self.addCleanup(self.right.close)
        self.console = Console(self.left.fileno(), Path(self.temp.name)/'console.bin')

    def test_marker_must_be_followed_by_prompt(self):
        def guest():
            self.right.recv(100)
            self.right.sendall(b'A>old prompt\r\nMARKER')
            time.sleep(.03)
            self.right.sendall(b'\r\nA>')
        thread = threading.Thread(target=guest)
        thread.start()
        data = self.console.command('TYPE HELLO.TXT', b'MARKER', 1)
        thread.join()
        self.assertTrue(data.endswith(b'A>'))
        self.assertEqual(self.console.path.read_bytes(), data)

    def test_stale_prompt_does_not_complete_a_new_command(self):
        def guest():
            self.right.recv(100)
            self.right.sendall(b'A>')
            time.sleep(.03)
            self.right.sendall(b'ERASE COPY.TXT\r\nA>')
        thread = threading.Thread(target=guest)
        thread.start()
        data = self.console.command('ERASE COPY.TXT', timeout=1)
        thread.join()
        self.assertIn(b'ERASE COPY.TXT', data)

    def test_missing_prompt_is_bounded(self):
        with self.assertRaises(TimeoutError): self.console.expect(b'A>', .02)

    def test_disconnect_is_failure(self):
        self.right.close()
        with self.assertRaises(RuntimeError): self.console.expect(b'A>', .1)

    def test_host_death_wins_over_stale_prompt(self):
        self.console.output.extend(b'A>')
        self.console.check = lambda: (_ for _ in ()).throw(RuntimeError('host died'))
        with self.assertRaisesRegex(RuntimeError, 'host died'):
            self.console.expect(b'A>', .1, 0)

    def test_invalid_deadlines(self):
        for value in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError): positive(value)


class OwnershipTests(unittest.TestCase):
    def test_duplicate_session_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'lock'
            with lock_session(path):
                with self.assertRaises(BlockingIOError): lock_session(path)
            with lock_session(path): pass

    def test_dirty_journal_prevents_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp)/'disk.img'
            Path(str(image)+'.jhj').write_bytes(b'pending')
            host = HostService('unused', 'unused', 0, image, 'unused', Path(temp), time.monotonic()+1)
            with patch('serial_session.subprocess.Popen') as spawn:
                with self.assertRaisesRegex(RuntimeError, 'unclean journal'): host.start()
                spawn.assert_not_called()


@unittest.skipUnless((ROOT.parent/'ravi/src/ravi').exists(), 'Ravi checkout required')
class BootstrapTests(unittest.TestCase):
    def exercise(self, broken=None, wrong_go=False):
        from importlib.resources import files
        from ravi.backends.robotron1715.monitor import IDENTITY
        payload = files('ravi.backends.robotron1715').joinpath('monitor.bin').read_bytes()
        code = bytes(range(256))*2
        memory = bytearray(65536)
        memory[0x4000:0x4000+len(payload)] = payload
        started = []
        class FakeMonitor:
            def __init__(self, wire): pass
            def response(self): return [IDENTITY]
            def read_memory(self, at, size):
                data = bytes(memory[at:at+size])
                if broken is not None and at == broken: return bytes([data[0]^1])+data[1:]
                return data
            def write_memory(self, at, data): memory[at:at+len(data)] = data
            def start(self, address):
                started.append(address)
                if wrong_go: raise RuntimeError('GO handoff failed; no replay')
        with tempfile.TemporaryDirectory() as temp:
            with patch('ravi.backends.robotron1715.boot.StockBoot') as boot, patch('ravi.backends.robotron1715.monitor.Monitor', FakeMonitor):
                if broken is not None or wrong_go:
                    with self.assertRaises(RuntimeError): bootstrap(object(), code, Path(temp), 1)
                else:
                    bootstrap(object(), code, Path(temp), 1)
                    self.assertEqual((Path(temp)/'platform-readback.bin').read_bytes(), code)
                self.assertEqual(boot.return_value.execute.call_count, 1)
        self.assertEqual(started, [] if broken is not None else [0xc033])

    def test_verified_handoff(self): self.exercise()
    def test_bad_monitor_never_starts_platform(self): self.exercise(0x4000)
    def test_bad_platform_never_starts_platform(self): self.exercise(0xc000)
    def test_failed_go_is_not_replayed(self): self.exercise(wrong_go=True)


class HardwarePreflightTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'build/platform.cim').exists(), 'build required')
    def test_classic_platform_is_rejected_before_device_open(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('check_serial_hardware.assert_device_unused') as device:
                with self.assertRaises(SystemExit) as error:
                    hardware_main(['--serial', '/not-opened', '--board', 'test',
                        '--out', str(Path(temp)/'campaign'), '--image', str(ROOT/'out/cpm-plus-1715.img'),
                        '--platform', str(ROOT/'build/platform.cim')])
                self.assertEqual(error.exception.code, 2)
                device.assert_not_called()
                self.assertFalse((Path(temp)/'campaign').exists())
