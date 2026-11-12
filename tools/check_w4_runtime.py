#!/usr/bin/env python3
"""MIT. Actual W4 ROM and CP/M at timed model rates; creates only private PTYs."""

import argparse
import hashlib
import json
import os
import pty
import re
import shutil
import subprocess
import tty
from pathlib import Path

from media import inspect, add
from banked_contract import source_fingerprint, validate_banked
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
    p.add_argument('--banked', action='store_true')
    p.add_argument('--extended', action='store_true')
    p.add_argument('--fault', choices=['header','payload','duplicate','foreign','missing-bank'])
    p.add_argument('--fragmented', action='store_true')
    p.add_argument('--read-only', action='store_true')
    p.add_argument('--corrupt-read', action='store_true')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    suffix = {9600: "9600", 41600: "fast", 62400: "62400"}[a.baud]
    image = ROOT / f"out/cpm-plus-1715-wm-{suffix}.img"
    code = b"" if a.banked else (ROOT / f"build/platform-wm-{suffix}.cim").read_bytes()
    if a.banked:
        image = ROOT / f"out/cpm-plus-1715-wm-banked-{suffix}.img"
        code = (ROOT / f"build/banked/platform-{suffix}.cim").read_bytes()
    if a.banked:
        validate_banked(image, ROOT/f'build/banked/platform-{suffix}.cim',
                        ROOT/f'build/banked/platform-{suffix}.json', a.baud)
    disk = a.out / "disk.img"
    shutil.copyfile(image, disk)
    if a.banked and a.extended:
        data = disk.read_bytes()
        for name, payload in [
            ('TPATEST.COM', (ROOT/'build/banked/tpa-test.cim').read_bytes()),
            ('DSKTEST.COM', (ROOT/'build/banked/disk-test.cim').read_bytes()),
            ('COLD.COM', bytes.fromhex('c300c6')),
            ('BIG.BIN', bytes((i*73 ^ (i>>8)) & 255 for i in range(80*1024)))]:
            data = add(data, name, payload)
        disk.write_bytes(data)
    if a.fragmented or a.fault:
        data = bytearray(disk.read_bytes())
        system = inspect(data)[(0,'CPM3.SYS')]
        if a.fragmented:
            # Move all system blocks and place its extents in reversed order at
            # the end of the directory; neither physical nor directory order matters.
            for index, block in enumerate(system.blocks):
                new = 380-index*2
                data[20480+new*2048:20480+(new+1)*2048] = data[20480+block*2048:20480+(block+1)*2048]
                data[20480+block*2048:20480+(block+1)*2048] = bytes([0xe5])*2048
                for slot in system.slots:
                    for off in range(slot+16,slot+32,2):
                        if int.from_bytes(data[off:off+2],'little') == block:
                            data[off:off+2] = new.to_bytes(2,'little')
            for index, slot in enumerate(system.slots):
                start = slot
                dest = 20480+(127-index)*32
                data[dest:dest+32] = data[start:start+32]
                data[start:start+32] = bytes([0xe5])*32
            system = inspect(data)[(0,'CPM3.SYS')]
        first = 20480+system.blocks[0]*2048
        if a.fault == 'header': data[first] ^= 1
        if a.fault == 'payload': data[first+256] ^= 1
        if a.fault == 'duplicate':
            start = system.slots[0]+16
            data[start+2:start+4] = data[start:start+2]
        if a.fault == 'foreign':
            start = inspect(data)[(0,'CCP.COM')].slots[0]+16
            data[start:start+2] = system.blocks[0].to_bytes(2,'little')
        disk.write_bytes(data)
    initial_disk = disk.read_bytes()
    wire, device = pty.openpty()
    terminal, console = pty.openpty()
    for fd in (wire, device, terminal, console):
        tty.setraw(fd)
    report = dict(
        hardware_executed=False,
        source_sha256=source_fingerprint(ROOT),
        probe_sha256=digest(ROOT/'build/wm-probe'),
        baud=a.baud,
        pty_transport_baud=9600,
        complete=False,
        image_sha256=digest(image),
        platform_sha256=hashlib.sha256(code).hexdigest(),
        host_sha256=digest(a.host),
        profile='banked' if a.banked else 'nonbanked',
        fault=a.fault, fragmented=a.fragmented, read_only=a.read_only,
        corrupt_read=a.corrupt_read,
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
        env=dict(os.environ, WM_ALIAS_BANK="4" if a.fault == "missing-bank" else ""),
    )
    host = None
    try:
        with SerialTransport(
            os.ttyname(device), 9600, parity="N", stop_bits=1, exclusive=True
        ) as port:
            m = identify_at_rate(port, 5)
            report["rom"] = m.identity
            assert m.identity["protocol"] == "W4" and m.identity["baud"] == a.baud
            m.write_memory(0xE000 if a.banked else 0xC000, code)
            if m.read_memory(0xE000 if a.banked else 0xC000, len(code)) != code:
                raise ValueError('platform readback mismatch')
            m.start(0xE033 if a.banked else 0xC033)
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
                    *( [] if a.read_only else ["--writable"] ),
                    *( ["--test-corrupt-read-reply-once"] if a.corrupt_read else [] ),
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
                if (emu.poll() is not None and not a.fault) or host.poll() is not None:
                    raise RuntimeError("emulator or host exited")

            c = Console(terminal, a.out / "console.bin", check)
            if a.fault:
                c.expect(b"CP/M 3 boot error", timeout=120, start=0)
                report['cases'].append('boot rejected '+a.fault)
                report['complete'] = True
                return
            c.expect(b"A>", timeout=120, start=0)
            report["cases"].append("cold boot")
            assert b"Robotron" in c.command("TYPE HELLO.TXT")
            if not a.read_only:
                c.command("PIP COPY.COM=CCP.COM")
                f = inspect(disk.read_bytes())
                assert f[(0, "COPY.COM")].data == f[(0, "CCP.COM")].data
                report["cases"].append("binary copy verified")
            c.warm_boot()
            report["cases"].append("warm boot")
            assert b"Robotron" in c.command("TYPE HELLO.TXT")
            if a.banked:
                c.command("PIP B:HELLO.TXT=A:HELLO.TXT")
                assert b"Robotron" in c.command("TYPE B:HELLO.TXT")
                c.warm_boot()
                assert b"Robotron" in c.command("TYPE B:HELLO.TXT")
                if not a.read_only:
                    c.command("PIP RAMCOPY.COM=B:HELLO.TXT")
                report["cases"].append("RAM disk and warm boot")
            if a.banked and a.extended:
                assert b'BANKED TPA PASS' in c.command('TPATEST')
                assert b'BANKED DISK PASS' in c.command('DSKTEST')
                report['cases'].extend(['advertised TPA verified', 'RAM disk full directory, full disk, random records and reuse'])
                c.command('PIP B:BIG.BIN=A:BIG.BIN')
                c.warm_boot()
                c.command('PIP BACK.BIN=B:BIG.BIN')
                files = inspect(disk.read_bytes())
                assert files[(0,'BACK.BIN')].data == files[(0,'BIG.BIN')].data
                report['cases'].append('80 KiB cross-bank roundtrip')
                c.command('COLD')
                assert b'No File' in c.command('DIR B:') or b'NO FILE' in c.output[-200:]
                report['cases'].append('cold boot clears RAM disk')
                at = len(c.output)
                c.command('SUBMIT TEST')
                c.expect(b'Native CP/M Plus on Robotron', start=at)
                c.expect(b'A>', start=c.output.index(b'Native CP/M Plus on Robotron', at))
                shown = c.command('SHOW')
                assert re.search(rb'B: RW, Space:\s+94k', shown), shown
                report['cases'].append('SUBMIT and SHOW')
            if a.read_only:
                assert b'ERROR' in c.command('PIP COPY.TXT=HELLO.TXT')
                assert disk.read_bytes() == initial_disk
                report['cases'].append('read-only media unchanged')
            if a.corrupt_read:
                logs = (a.out/'host.log').read_text()
                assert 'injected=1' in logs and 'duplicate-valid-reply=1' in logs
                report['cases'].append('corrupt disk CRC recovered')
            report["complete"] = True
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
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
