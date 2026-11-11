#!/usr/bin/env python3
"""MIT. W4 cold discovery and matched serial-only CP/M boot; no RAM clock shim."""

import argparse
import json
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ravi.backends.robotron1715w.discovery import configure_rate, identify_at_rate
from ravi.transport import LoggedTransport, SerialTransport
from serial_session import lock_session, validate_artifacts
from serial_wm import ROOT, digest, host_command


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["boot", "attach"])
    p.add_argument("--serial", required=True)
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--console-pty", required=True)
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--baud", type=int, choices=[9600, 41600, 62400], default=62400)
    p.add_argument("--read-only", action="store_true")
    a = p.parse_args()
    a.test_corrupt_read_reply_once = False
    suffix = {9600: "9600", 41600: "fast", 62400: "62400"}[a.baud]
    a.image = ROOT / f"out/cpm-plus-1715-wm-{suffix}.img"
    a.platform = ROOT / f"build/platform-wm-{suffix}.cim"
    _, code = validate_artifacts(a.image, a.platform)
    divisor = {9600: 13, 41600: 3, 62400: 2}[a.baud]
    if bytes.fromhex(f"3e47d309d30a3e{divisor:02x}d309d30a") not in code:
        raise ValueError("Platform clock does not match requested rate")
    session = a.session.resolve()
    identity = dict(
        machine="robotron1715w",
        protocol="W4",
        baud=a.baud,
        framing="8N1",
        image_sha256=digest(a.image),
        platform_sha256=digest(a.platform),
        host_sha256=digest(a.host),
        read_only=a.read_only,
    )
    if a.mode == "boot":
        session.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(a.image, session / "disk.img")
        (session / "identity.json").write_text(json.dumps(identity, indent=2))
    else:
        if json.loads((session / "identity.json").read_text()) != identity:
            raise ValueError("Session identity mismatch")
        if (session / "disk.img").stat().st_size != 819200:
            raise ValueError("Invalid disk size")
    report = {"complete": False, "monitor_byte_delay_ms": 0, "baud": a.baud}
    with (
        lock_session(session / "session.lock"),
        SerialTransport(
            a.serial, 9600, parity="N", stop_bits=1, exclusive=True
        ) as port,
    ):
        child = None
        try:
            report["rate"] = configure_rate(port, a.serial, a.baud)
            if a.mode == "boot":
                with (
                    (session / "bootstrap-rx.bin").open("wb") as rx,
                    (session / "bootstrap-tx.bin").open("wb") as tx,
                ):
                    wire = LoggedTransport(port, rx, tx)
                    m = identify_at_rate(wire, 5)
                    report["rom"] = m.identity
                    if m.identity["protocol"] != "W4" or m.identity["baud"] != a.baud:
                        raise ValueError("Expected W4 at selected rate")
                    print(json.dumps({"rom": m.identity}), flush=True)
                    m.write_memory(0xC000, code)
                    actual = m.read_memory(0xC000, len(code))
                    (session / "platform-readback.bin").write_bytes(actual)
                    if actual != code:
                        raise ValueError("Platform readback mismatch")
                    m.start(0xC033)
                    report["events"] = m.events
                    report["complete"] = True
            command = host_command(a, session, port.fd) + ["--disk-baud", str(a.baud)]
            report["command"] = command
            (session / f"launch-{time.time_ns()}.json").write_text(
                json.dumps(report, indent=2)
            )
            child = subprocess.Popen(command, pass_fds=(port.fd,))

            def stop(signum, frame):
                raise KeyboardInterrupt

            previous = signal.signal(signal.SIGTERM, stop)
            try:
                return child.wait()
            except KeyboardInterrupt:
                return 130
            finally:
                signal.signal(signal.SIGTERM, previous)
        finally:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            (session / "latest-launch.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
