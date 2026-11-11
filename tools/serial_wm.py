#!/usr/bin/env python3
"""MIT. Explicit W/M serial-only boot and runtime attach; no port discovery."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import termios
import time
from ravi.transport import SerialTransport, LoggedTransport
from ravi.backends.robotron1715w.host import Monitor, MonitorError
from ravi.backends.robotron1715w import protocol as protocol
from ravi.backends.robotron1715w.build import ROOT as ROM_ROOT
from serial_session import validate_artifacts, lock_session

ROOT = Path(__file__).resolve().parents[1]
W2_ID = "4f81c5516ba23bbc"
# PC001 tested clock shim: CTC1/2 timer /16 constant13; SIO B x16 8N1; W2 idle.
SHIM = bytes.fromhex(
    "f3 3e07 d309 d30a 3e0d d309 d30a af d30f 3e04 d30f 3e44 d30f c35001"
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def switch_baud(port, baud):
    attrs = termios.tcgetattr(port.fd)
    attrs[4] = attrs[5] = getattr(termios, f"B{baud}")
    termios.tcsetattr(port.fd, termios.TCSANOW, attrs)
    if termios.tcgetattr(port.fd)[4:6] != attrs[4:6]:
        raise RuntimeError("serial rate readback failed")


def legacy_retry(action, monitor, attempts, evidence):
    for attempt in range(attempts):
        try:
            return action()
        except (TimeoutError, MonitorError) as exc:
            if not monitor.usable or (
                isinstance(exc, MonitorError)
                and exc.reply.status
                not in (protocol.UART, protocol.BAD_CRC, protocol.TIMEOUT)
            ):
                raise
            evidence.append(dict(attempt=attempt + 1, error=str(exc)))
            if attempt + 1 == attempts:
                raise
            # Allow any partial W2 frame to expire. Only scratch writes and
            # read-only operations may enter this retry wrapper, never GO.
            time.sleep(1)


def bootstrap(port, profile, platform, session, w2_at_1200=False):
    report = dict(profile=profile, retries=[], complete=False)
    with (session / "bootstrap-tx.bin").open("wb") as tx, (
        session / "bootstrap-rx.bin"
    ).open("wb") as rx:
        wire = LoggedTransport(port, rx, tx)
        m = Monitor(wire, 5)
        # Permit ROM self-test/display startup before the first request.
        # Startup frames remain captured and are parsed by identify().
        time.sleep(1)
        try:
            if profile == "w2" and not w2_at_1200:
                info = legacy_retry(m.identify, m, 5, report["retries"])
                if info.get("protocol") != "W2" or info.get("build_id") != W2_ID:
                    raise ValueError(
                        "W2 compatibility requires the qualified PC001 W2 fingerprint"
                    )
                report["before_switch"] = info
                for offset, byte in enumerate(SHIM):
                    legacy_retry(
                        lambda: m.write_memory(0x8000 + offset, bytes([byte])),
                        m,
                        8,
                        report["retries"],
                    )
                actual = legacy_retry(
                    lambda: m.read_memory(0x8000, len(SHIM)), m, 5, report["retries"]
                )
                if actual != SHIM:
                    raise ValueError("shim readback failed; not executed")
                (session / "shim-readback.bin").write_bytes(actual)
                m.start(0x8000)  # never replay: STARTED then no cooperative return
                time.sleep(0.1)
                switch_baud(port, 1200)
                m = Monitor(wire, 5)
            info = m.identify()
            expected = "W2" if profile == "w2" else "W3"
            metadata = json.loads(
                (
                    ROM_ROOT / ("rom.json" if profile == "w2" else "rom-w3.json")
                ).read_text()
            )
            if info["protocol"] != expected or info["build_id"] != metadata["build_id"]:
                raise ValueError("unexpected ROM build; no platform upload")
            report["identity"] = info
            m.write_memory(0xC000, platform)
            actual = m.read_memory(0xC000, len(platform))
            (session / "platform-readback.bin").write_bytes(actual)
            if actual != platform:
                raise ValueError("platform readback mismatch; not executed")
            m.start(0xC033)
            report["complete"] = True
            return info
        except Exception as exc:
            report["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            report["events"] = m.events
            (session / "bootstrap.json").write_text(json.dumps(report, indent=2) + "\n")


def host_command(args, session, fd=None):
    stamp = str(time.time_ns())
    command = [
        str(args.host.resolve()),
        "--machine",
        "robotron1715w",
        "--resume-disk",
        "--timeout",
        "1800",
        "--serial",
        args.serial,
        "--volume",
        str(session / "disk.img"),
        "--console-pty",
        args.console_pty,
        "--log",
        str(session / f"host-{stamp}.log"),
        "--capture",
        str(session / f"wire-{stamp}.bin"),
    ]
    if not args.read_only:
        command.append("--writable")
    if args.test_corrupt_read_reply_once:
        command.append("--test-corrupt-read-reply-once")
    if fd is not None:
        command += ["--serial-fd", str(fd)]
    return command


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["boot", "attach"])
    p.add_argument("--serial", required=True)
    p.add_argument("--rom-profile", choices=["w2", "w3"], required=True)
    p.add_argument(
        "--w2-at-1200",
        action="store_true",
        help="W2 monitor already has the verified temporary clock correction",
    )
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--console-pty", required=True)
    p.add_argument("--image", type=Path, default=ROOT / "out/cpm-plus-1715-wm.img")
    p.add_argument("--platform", type=Path, default=ROOT / "build/platform-wm.cim")
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--read-only", action="store_true")
    p.add_argument(
        "--test-corrupt-read-reply-once",
        action="store_true",
        help="qualification only: inject one disk CRC error",
    )
    a = p.parse_args()
    if a.w2_at_1200 and (a.mode != "boot" or a.rom_profile != "w2"):
        p.error("--w2-at-1200 requires boot with --rom-profile w2")
    _, platform = validate_artifacts(a.image, a.platform)
    if not a.host.is_file():
        p.error("native host executable not found")
    session = a.session.resolve()
    identity = dict(
        machine="robotron1715w",
        format="1200 8N1",
        rom_profile=a.rom_profile,
        image_sha256=digest(a.image),
        platform_sha256=digest(a.platform),
        host_sha256=digest(a.host),
        read_only=a.read_only,
    )
    if a.mode == "boot":
        session.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(a.image, session / "disk.img")
        (session / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    else:
        old = json.loads((session / "identity.json").read_text())
        if any(old.get(k) != v for k, v in identity.items()):
            p.error("session identity mismatch")
        if (session / "disk.img").stat().st_size != 819200:
            p.error("invalid session disk")
    # Supervisor retains the lock across native-host descriptor adoption.
    with lock_session(session / "session.lock"), SerialTransport(
        a.serial,
        (
            9600
            if a.mode == "boot" and a.rom_profile == "w2" and not a.w2_at_1200
            else 1200
        ),
        parity="N",
        stop_bits=1,
        exclusive=True,
    ) as port:
        if a.mode == "boot":
            identity["rom"] = bootstrap(
                port, a.rom_profile, platform, session, a.w2_at_1200
            )
            (session / "identity.json").write_text(
                json.dumps(identity, indent=2) + "\n"
            )
        child = subprocess.Popen(host_command(a, session, port.fd), pass_fds=(port.fd,))

        def stop(signum, frame):
            raise KeyboardInterrupt

        prior = signal.signal(signal.SIGTERM, stop)
        try:
            return child.wait()
        except KeyboardInterrupt:
            return 130
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            signal.signal(signal.SIGTERM, prior)


if __name__ == "__main__":
    raise SystemExit(main())
