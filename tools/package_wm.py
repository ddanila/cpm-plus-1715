#!/usr/bin/env python3
"""Package matched W/M binaries and completed emulator evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ravi", type=Path, required=True)
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--reports", type=Path, nargs="+", required=True)
    a = p.parse_args()
    files = {
        "platform-wm.cim": ROOT / "build/platform-wm.cim",
        "cpm-plus-1715-wm.img": ROOT / "out/cpm-plus-1715-wm.img",
        "jukuhost": a.host,
        "README.md": ROOT / "docs/wm-serial.md",
        "dependencies.json": ROOT / "tools/wm-dependencies.json",
    }
    for name, path in {
        "LICENSE": ROOT / "LICENSE",
        "NOTICE.md": ROOT / "NOTICE.md",
        "JUKU-LICENSE": ROOT / "third_party/JUKU-LICENSE",
        "JUKU-COMMON-LICENSE": ROOT / "third_party/juku-common/LICENSE-BSD-2-Clause",
        "CPM-LICENSE.md": ROOT / "third_party/cpm3/LICENSE.md",
    }.items():
        files[name] = path
    for name in ("rom-w3.bin", "rom-w3.json"):
        files[name] = a.ravi / "src/ravi/backends/robotron1715w" / name
    for name in ("serial_wm.py", "serial_session.py", "media.py"):
        files["tools/" + name] = ROOT / "tools" / name

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    coverage = set()
    profiles = set()
    for index, path in enumerate(a.reports):
        report = json.loads(path.read_text())
        if not report["complete"] or report["hardware_executed"]:
            raise ValueError("requires completed emulator qualification")
        coverage.update(report["cases"])
        profiles.add(report["rom_profile"])
        rom = (
            a.ravi
            / "src/ravi/backends/robotron1715w"
            / ("rom.bin" if report["rom_profile"] == "w2" else "rom-w3.bin")
        )
        if report["rom_sha256"] != digest(rom):
            raise ValueError("report ROM mismatch")
        for key, file in [
            ("platform_sha256", "platform-wm.cim"),
            ("image_sha256", "cpm-plus-1715-wm.img"),
            ("host_sha256", "jukuhost"),
        ]:
            if report[key] != digest(files[file]):
                raise ValueError("report artifact mismatch: " + file)
        files[f'reports/{index}-{report["rom_profile"]}.json'] = path
    required = {
        "binary copy verified independently",
        "host restart without target reset",
        "warm boot",
        "read-only media unchanged",
        "corrupt disk CRC recovered with duplicate reply",
    }
    if profiles != {"w2", "w3"} or not required <= coverage:
        raise ValueError("missing W2/W3, writable/read-only or recovery qualification")
    manifest = dict(
        version="wm-0.1.0",
        hardware_qualified=False,
        files={name: digest(path) for name, path in files.items()},
    )
    output = ROOT / "out/cpm-plus-1715-wm.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in files.items():
            archive.write(path, name)
        archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
