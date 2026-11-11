"""W/M handoff recovery boundaries; no physical ports."""

import sys
import unittest
import tempfile
from unittest.mock import patch, call
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    from serial_wm import legacy_retry, host_command, bootstrap, SHIM

    HAVE_RAVI = True
except ModuleNotFoundError as exc:
    if exc.name != "ravi":
        raise
    HAVE_RAVI = False


@unittest.skipUnless(HAVE_RAVI, "install pinned Ravi for W/M tests")
class WmSessionTests(unittest.TestCase):
    def test_retry_is_bounded_and_unknown_execution_is_not_replayed(self):
        calls = []

        def lost():
            calls.append(1)
            raise TimeoutError("lost")

        with self.assertRaises(TimeoutError):
            legacy_retry(lost, SimpleNamespace(usable=False), 8, [])
        self.assertEqual(len(calls), 1)
        with self.assertRaises(TimeoutError):
            legacy_retry(lost, SimpleNamespace(usable=True), 1, [])
        self.assertEqual(len(calls), 2)

    def test_runtime_adopts_descriptor_and_keeps_explicit_profile(self):
        args = SimpleNamespace(
            host=Path("/tmp/host"),
            serial="/dev/example",
            console_pty="/dev/console-example",
            read_only=True,
            test_corrupt_read_reply_once=False,
        )
        command = host_command(args, Path("/tmp/session"), 17)
        self.assertIn("robotron1715w", command)
        self.assertEqual(command[-2:], ["--serial-fd", "17"])
        self.assertNotIn("--writable", command)
        self.assertIn("--resume-disk", command)
        self.assertEqual(len(SHIM), 27)

    def test_already_corrected_w2_verifies_identity_before_platform_only_handoff(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "serial_wm.Monitor"
        ) as cls, patch("serial_wm.time.sleep"):
            monitor = cls.return_value
            monitor.events = []
            monitor.identify.return_value = {
                "protocol": "W2",
                "build_id": "4f81c5516ba23bbc",
            }
            monitor.read_memory.return_value = b"platform"
            bootstrap(object(), "w2", b"platform", Path(directory), True)
            monitor.write_memory.assert_called_once_with(0xC000, b"platform")
            monitor.start.assert_called_once_with(0xC033)

    def test_already_corrected_w2_rejects_unknown_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "serial_wm.Monitor"
        ) as cls, patch("serial_wm.time.sleep"):
            monitor = cls.return_value
            monitor.events = []
            monitor.identify.return_value = {"protocol": "W2", "build_id": "unknown"}
            with self.assertRaises(ValueError):
                bootstrap(object(), "w2", b"platform", Path(directory), True)
            monitor.write_memory.assert_not_called()
            monitor.start.assert_not_called()

    def test_cold_w2_reuses_verified_shim_and_executes_each_stage_once(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "serial_wm.Monitor"
        ) as cls, patch("serial_wm.time.sleep"), patch("serial_wm.switch_baud") as baud:
            monitor = cls.return_value
            monitor.events = []
            monitor.identify.return_value = {
                "protocol": "W2",
                "build_id": "4f81c5516ba23bbc",
            }
            monitor.read_memory.side_effect = [bytes([b]) for b in SHIM] + [
                SHIM,
                b"platform",
            ]
            port = object()
            bootstrap(port, "w2", b"platform", Path(directory))
            monitor.write_memory.assert_called_once_with(0xC000, b"platform")
            self.assertEqual(monitor.start.call_args_list, [call(0x8000), call(0xC033)])
            baud.assert_called_once_with(port, 1200)
