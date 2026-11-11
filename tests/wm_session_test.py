"""W/M handoff recovery boundaries; no physical ports."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    from serial_wm import legacy_retry, host_command, SHIM

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
