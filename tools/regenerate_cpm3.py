#!/usr/bin/env python3
"""Generate the nonbanked 1715 CPM3.SYS with pinned DRI tools.
Adapted from cpm-plus-juku; BSD-2-Clause, third_party/JUKU-LICENSE.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import pexpect


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "third_party" / "cpm3"
RELEASES = INPUTS / "releases"
DEFAULT_ZXCC = ROOT / "build" / "bin" / "zxcc"

ARCHIVES = {
    "source": (
        RELEASES / "cpm3src_unix-20260607.zip",
        "d90cda1f25112ace3b436c4054304ace423331caa1f034c44f26698728a9fdb7",
    ),
    "binary": (
        RELEASES / "cpm3bin_unix-20260607.zip",
        "ec24f6e1fa173d33bcd2555dfae8296471fc8ea144c72e8cbe2166971451da82",
    ),
}
TOOLS = {
    "RMAC.COM": ("source", "rmac.com",
                 "d3132c8e356d0c8e71b53757445e7ef89e55dfda9dbda11c48cf7ede6c2c40f3"),
    "LINK.COM": ("source", "drlink.com",
                 "714115910168df0900a41698551d518c921fe8329dae78378756f2445a4dc175"),
    "GENCPM.COM": ("binary", "gencpm.com",
                   "3a71036c6a6571f62dcb93f9434c140354d3601d17cabc0d38702811b2a33d87"),
}

# GENCPM stores its printable serial at header 35h and initializes the SCB date
# at runtime FE58h.  The qualified Juku images intentionally contain no DRI
# serial in the distribution header and retain the CP/M Plus 3.0 release date.
HEADER_SERIAL = slice(0x35, 0x3B)
GENCPM_INITIAL_DATE = bytes((0x12, 0x07))  # 1982-12-15, CP/M day 0712h
JUKU_INITIAL_DATE = bytes((0xB5, 0x06))    # 1982-09-13, CP/M day 06B5h


def tool(directory: Path, name: str) -> Path:
    for candidate in (directory / name.lower(), directory / name.upper()):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"{name} is missing from {directory}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_tools(destination: Path) -> None:
    archives: dict[str, zipfile.ZipFile] = {}
    try:
        for key, (path, expected) in ARCHIVES.items():
            data = path.read_bytes()
            actual = sha256(data)
            if actual != expected:
                raise RuntimeError(
                    f"{path} SHA-256 {actual} != pinned {expected}"
                )
            archives[key] = zipfile.ZipFile(path)
        for output, (archive, member, expected) in TOOLS.items():
            data = archives[archive].read(member)
            actual = sha256(data)
            if actual != expected:
                raise RuntimeError(
                    f"{member} SHA-256 {actual} != pinned {expected}"
                )
            (destination / output).write_bytes(data)
    finally:
        for archive in archives.values():
            archive.close()


def dos_text(source: Path, destination: Path,
             replacements: dict[str, str] | None = None) -> None:
    text = source.read_text().replace("\r\n", "\n").replace("\r", "\n")
    for old, new in (replacements or {}).items():
        if text.count(old) != 1:
            raise RuntimeError(f"cannot replace unique source text {old!r}")
        text = text.replace(old, new)
    destination.write_bytes(text.replace("\n", "\r\n").encode("ascii"))


def run(command: list[str], work: Path) -> None:
    subprocess.run(command, cwd=work, check=True)


def generate(zxcc: Path, work: Path, *, top_page: int,
             adapter_address: int) -> None:
    child = pexpect.spawn(
        str(zxcc), ["GENCPM.COM"], cwd=str(work), encoding="latin1",
        timeout=15,
    )
    answers = (
        ("Use GENCPM.DAT", "Y"),
        ("Create a new", "N"),
        ("Display Load Map", ""),
        ("console columns", ""),
        ("lines in console", ""),
        ("Backspace", ""),
        ("Rubout", ""),
        ("default drive", ""),
        ("Top page", f"{top_page:02X}"),
        ("Bank switched", ""),
        ("Double allocation vectors", ""),
        ("Accept new", ""),
    )
    transcript = ""
    for prompt, answer in answers:
        child.expect(prompt)
        transcript += child.before + child.after
        child.sendline(answer)
    child.expect(pexpect.EOF)
    transcript += child.before
    print(transcript)
    bios = adapter_address - 0x400
    bdos = bios - 0x1F00
    if f"BIOS3    SPR  {bios:04X}H  0400H" not in transcript or \
            f"BDOS3    SPR  {bdos:04X}H  1F00H" not in transcript:
        raise RuntimeError("GENCPM produced an unexpected non-banked map")


def normalize(result: bytes, *, adapter_address: int,
              metadata_policy: str) -> bytes:
    data = bytearray(result)
    serial = bytes(data[HEADER_SERIAL])
    if serial != b"654321":
        raise RuntimeError(f"unexpected GENCPM header serial {serial!r}")

    # SYS payload records are stored from the top of common memory downward.
    # Translate runtime FE58h relative to the system's configured memory top.
    # The SCB resides at BIOS entry minus 64h; its date field is +58h.
    runtime_date = adapter_address - 0x400 - 0x64 + 0x58
    record = (adapter_address - 1 - runtime_date) // 128
    within = runtime_date - (adapter_address - (record + 1) * 128)
    offset = 256 + record * 128 + within
    actual = bytes(data[offset:offset + 2])
    if actual != GENCPM_INITIAL_DATE:
        raise RuntimeError(
            f"unexpected GENCPM initial SCB date {actual.hex()} at {offset:#x}"
        )
    if metadata_policy == "qualified":
        data[HEADER_SERIAL] = bytes(6)
        data[offset:offset + 2] = JUKU_INITIAL_DATE
    elif metadata_policy != "gencpm":
        raise ValueError(f"unknown metadata policy {metadata_policy!r}")
    return bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zxcc", type=Path, default=DEFAULT_ZXCC)
    parser.add_argument(
        "--tools", type=Path,
        help="optional external directory containing RMAC.COM, LINK.COM, and GENCPM.COM",
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "build" / "cpm3.sys",
    )
    parser.add_argument("--adapter-address", type=lambda value: int(value, 0),
                        default=0xC000)
    parser.add_argument("--top-page", type=lambda value: int(value, 0),
                        default=0xBF)
    parser.add_argument(
        "--check", action="store_true",
        help="compare the regenerated bytes with --output instead of writing",
    )
    parser.add_argument(
        "--metadata-policy", choices=("gencpm",),
        default="gencpm",
        help="qualified A000h baseline normalization or untouched GENCPM metadata",
    )
    args = parser.parse_args()
    if args.adapter_address != 0xC000 or \
            args.top_page != (args.adapter_address >> 8) - 1:
        raise ValueError("top page must end immediately below the adapter")
    zxcc = args.zxcc.resolve()
    if not zxcc.is_file():
        raise FileNotFoundError(zxcc)

    with tempfile.TemporaryDirectory(prefix="cpm-plus-juku-build.") as name:
        work = Path(name)
        for filename in ("bdos3.spr", "gencpm.dat"):
            shutil.copy2(INPUTS / filename, work / filename)
        if args.tools is None:
            extract_tools(work)
        else:
            for filename in ("RMAC.COM", "LINK.COM", "GENCPM.COM"):
                shutil.copy2(tool(args.tools, filename), work / filename)
        adapter_source = "adapter         equ     0a000h"
        replacements = {
            adapter_source: f"adapter         equ     0{args.adapter_address:04x}h",
        }
        dos_text(
            ROOT / "src" / "cpm3-bios.asm", work / "jbios.asm",
            replacements,
        )
        dos_text(INPUTS / "scb.asm", work / "scb.asm")
        run([str(zxcc), "RMAC.COM", "jbios"], work)
        run([str(zxcc), "RMAC.COM", "scb"], work)
        run([str(zxcc), "LINK.COM", "bios3[os]=jbios,scb"], work)
        generate(zxcc, work, top_page=args.top_page,
                 adapter_address=args.adapter_address)
        result = normalize(
            (work / "cpm3.sys").read_bytes(),
            adapter_address=args.adapter_address,
            metadata_policy=args.metadata_policy,
        )

    expected_header = bytes((
        args.adapter_address >> 8, 0x23, 0, 0,
        (args.adapter_address - 0x400) & 0xFF,
        (args.adapter_address - 0x400) >> 8,
    ))
    if result[:6] != expected_header or len(result) != 9216:
        raise RuntimeError("generated CPM3.SYS has an unexpected header")
    if args.check:
        expected = args.output.read_bytes()
        if result != expected:
            mismatch = next(
                index for index, pair in enumerate(zip(result, expected))
                if pair[0] != pair[1]
            ) if len(result) == len(expected) else min(len(result), len(expected))
            raise RuntimeError(
                f"{args.output} differs from regenerated image at {mismatch:#x}"
            )
        print(f"CPM3-SYS-REGEN: PASS {args.output} ({len(result)} bytes)")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(result)
        print(f"wrote {args.output} ({len(result)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
