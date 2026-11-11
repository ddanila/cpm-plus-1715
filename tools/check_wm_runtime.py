#!/usr/bin/env python3
"""Headless W/M actual-ROM/platform/CPM qualification with native host and PTYs."""

import argparse, hashlib, json, os, pty, select, signal, subprocess, sys, time, tty
from pathlib import Path
from media import inspect

ROOT = Path(__file__).resolve().parents[1]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--rom-profile", choices=["w2", "w3"], default="w3")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--read-only", action="store_true")
    p.add_argument("--corrupt-read", action="store_true")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    wire, device = pty.openpty()
    terminal, console = pty.openpty()
    for fd in (wire, device, terminal, console):
        tty.setraw(fd)
    log = (a.out / "emulator.log").open("wb")
    hostlog = (a.out / "host-process.log").open("wb")
    emu = subprocess.Popen(
        [str(ROOT / "build/wm-probe"), str(a.rom), str(wire), str(a.out / "ram.bin")],
        pass_fds=(wire,),
        stderr=log,
    )
    host = None
    output = bytearray()
    cases = []
    image = ROOT / "out/cpm-plus-1715-wm.img"
    session = a.out / "session"
    result = dict(
        complete=False,
        hardware_executed=False,
        cases=cases,
        rom_sha256=digest(a.rom),
        platform_sha256=digest(ROOT / "build/platform-wm.cim"),
        image_sha256=digest(image),
        host_sha256=digest(a.host),
        emulator_sha256=digest(ROOT / "build/wm-probe"),
        rom_profile=a.rom_profile,
    )

    def passed(name):
        cases.append(name)
        print(name, "PASS", flush=True)

    def expect(marker, start=0, timeout=240):
        end = time.monotonic() + timeout
        while marker not in output[start:]:
            if emu.poll() is not None or (host and host.poll() is not None):
                raise RuntimeError("child exited; inspect host-process.log")
            if time.monotonic() > end:
                raise TimeoutError(bytes(output[-600:]))
            if select.select([terminal], [], [], 0.05)[0]:
                output.extend(os.read(terminal, 8192))
                (a.out / "console.bin").write_bytes(output)
        return bytes(output[start:])

    def command(text):
        at = len(output)
        os.write(terminal, text.encode() + b"\r")
        data = expect(b"A>", at)
        passed(text)
        return data

    def start(mode):
        return subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tools/serial_wm.py"),
                mode,
                "--host",
                str(a.host),
                "--serial",
                os.ttyname(device),
                "--rom-profile",
                a.rom_profile,
                "--session",
                str(session),
                "--console-pty",
                os.ttyname(console),
            ]
            + (["--read-only"] if a.read_only else [])
            + (
                ["--test-corrupt-read-reply-once"]
                if a.corrupt_read and mode == "boot"
                else []
            ),
            stdout=hostlog,
            stderr=hostlog,
            env=dict(os.environ, JH_TEST_PTY_UNPACED="1"),
        )

    try:
        host = start("boot")
        expect(b"A>")
        passed("CP/M Plus cold boot without video or drives")
        assert b"Robotron 1715" in command("TYPE HELLO.TXT")
        command("DIR")
        disk = session / "disk.img"
        if a.read_only:
            before = digest(disk)
            reply = command("PIP COPY.TXT=HELLO.TXT")
            assert b"ERROR" in reply and digest(disk) == before
            passed("read-only media unchanged")
        else:
            command("PIP COPY.TXT=HELLO.TXT")
            files = inspect(disk.read_bytes())
            assert files[(0, "COPY.TXT")].data == files[(0, "HELLO.TXT")].data
            command("PIP BINCOPY.COM=CCP.COM")
            files = inspect(disk.read_bytes())
            assert files[(0, "BINCOPY.COM")].data == files[(0, "CCP.COM")].data
            passed("binary copy verified independently")
            command("RENAME RENAMED.TXT=COPY.TXT")
            assert (0, "RENAMED.TXT") in inspect(disk.read_bytes())
            at = len(output)
            os.write(terminal, b"\x03")
            expect(b"A>", at)
            passed("warm boot")
            host.terminate()
            host.wait(timeout=15)
            host = None
            host = start("attach")
            time.sleep(0.5)
            assert b"Robotron" in command("TYPE RENAMED.TXT")
            passed("host restart without target reset")
            command("ERASE RENAMED.TXT")
            assert (0, "RENAMED.TXT") not in inspect(disk.read_bytes())
        for log_path in session.glob("host-*.log"):
            assert "phase=netdisk serial=1200 8N1" in log_path.read_text()
        passed("runtime framing remains 1200 8N1 after handoff")
        assert digest(image) == result["image_sha256"]
        passed("source image unchanged")
        if a.corrupt_read:
            logs = "".join(p.read_text() for p in session.glob("host-*.log"))
            assert "injected=1" in logs and "duplicate-valid-reply=1" in logs
            passed("corrupt disk CRC recovered with duplicate reply")
        result["complete"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if host and host.poll() is None:
            host.terminate()
            host.wait(timeout=15)
        emu.terminate()
        emu.wait(timeout=10)
        log.close()
        hostlog.close()
        result["emulator_exit"] = emu.returncode
        (a.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        for fd in (wire, device, terminal, console):
            os.close(fd)


if __name__ == "__main__":
    main()
