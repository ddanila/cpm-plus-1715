#!/usr/bin/env python3
"""MIT. Actual W4 ROM and CP/M at timed model rates; creates only private PTYs."""

import argparse
import json
import os
import pty
import shutil
import subprocess
import tty
from pathlib import Path

from media import inspect
from ravi.backends.robotron1715w.discovery import identify_at_rate
from ravi.transport import SerialTransport
from serial_session import Console, digest

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--baud", type=int, choices=[9600, 41600, 62400], default=62400)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    suffix = {9600: "9600", 41600: "fast", 62400: "62400"}[a.baud]
    image = ROOT / f"out/cpm-plus-1715-wm-{suffix}.img"
    code = (ROOT / f"build/platform-wm-{suffix}.cim").read_bytes()
    disk = a.out / "disk.img"
    shutil.copyfile(image, disk)
    wire, device = pty.openpty()
    terminal, console = pty.openpty()
    for fd in (wire, device, terminal, console):
        tty.setraw(fd)
    report = dict(
        hardware_executed=False,
        baud=a.baud,
        pty_transport_baud=9600,
        complete=False,
        image_sha256=digest(image),
        rom_sha256=digest(a.rom),
        cases=[],
    )
    elog = (a.out / "emulator.log").open("wb")
    hlog = (a.out / "host-process.log").open("wb")
    emu = subprocess.Popen(
        [
            str(ROOT / "build/wm-probe"),
            str(a.rom),
            str(wire),
            str(a.out / "ram.bin"),
            str(a.baud),
        ],
        pass_fds=(wire,),
        stderr=elog,
    )
    host = None
    try:
        with SerialTransport(
            os.ttyname(device), 9600, parity="N", stop_bits=1, exclusive=True
        ) as port:
            m = identify_at_rate(port, 5)
            report["rom"] = m.identity
            assert m.identity["protocol"] == "W4" and m.identity["baud"] == a.baud
            m.write_memory(0xC000, code)
            m.start(0xC033)
            # PTY has no bit rate: the emulator independently clocks the wire at a.baud.
            host = subprocess.Popen(
                [
                    str(a.host),
                    "--machine",
                    "robotron1715w",
                    "--resume-disk",
                    "--disk-baud",
                    "9600",
                    "--serial",
                    os.ttyname(device),
                    "--serial-fd",
                    str(port.fd),
                    "--volume",
                    str(disk),
                    "--writable",
                    "--console-pty",
                    os.ttyname(console),
                    "--log",
                    str(a.out / "host.log"),
                    "--capture",
                    str(a.out / "wire.bin"),
                ],
                pass_fds=(port.fd,),
                stdout=hlog,
                stderr=hlog,
                env=dict(os.environ, JH_TEST_PTY_UNPACED="1"),
            )

            def check():
                if emu.poll() is not None or host.poll() is not None:
                    raise RuntimeError("emulator or host exited")

            c = Console(terminal, a.out / "console.bin", check)
            c.expect(b"A>", timeout=120, start=0)
            report["cases"].append("cold boot")
            assert b"Robotron" in c.command("TYPE HELLO.TXT")
            c.command("PIP COPY.COM=CCP.COM")
            f = inspect(disk.read_bytes())
            assert f[(0, "COPY.COM")].data == f[(0, "CCP.COM")].data
            report["cases"].append("binary copy verified")
            c.warm_boot()
            report["cases"].append("warm boot")
            assert b"Robotron" in c.command("TYPE HELLO.TXT")
            report["complete"] = True
    finally:
        if host and host.poll() is None:
            host.terminate()
            host.wait(timeout=10)
        emu.terminate()
        emu.wait(timeout=10)
        elog.close()
        hlog.close()
        for fd in (wire, device, terminal, console):
            os.close(fd)
        (a.out / "result.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
