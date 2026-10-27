# CP/M Plus 3.1 for Robotron 1715

Native, nonbanked CP/M Plus for the ordinary 64 KB Robotron 1715, using the
classic PIO floppy-controller interface. This is a new OS port, not a patched
1715W disk. The BIOS and bootstrap execute on the emulated Z80; no host service
intercepts BDOS calls or injects disk records into guest RAM.

## Build

On Debian/Ubuntu install `build-essential bison python3 python3-pexpect`.
Run `make all test`. The pinned DRI tools run under a locally built ZXCC; zmac
is also built from source. No sibling Juku checkout is required.

Outputs:

- `out/cpm-plus-1715.img`: fresh 80×2×5×1024 raw A: disk.
- `build/cpm3.sys`: generated nonbanked system.
- `build/system-map.json`: resident map and system checksum.
- `build/test.rom`: original CI fixture, **not a replacement hardware ROM**.

The image includes CCP, DIR, TYPE, PIP, ERASE, RENAME, SHOW, SET, SUBMIT and a
small text/batch demonstration. For example: `TYPE HELLO.TXT`,
`PIP COPY.TXT=HELLO.TXT`, or `SUBMIT TEST`.

## Emulator qualification

Check out the exact Pico1715 and DAC revisions in `dependencies.json` into
sibling directories (or pass `PICO=/path` and `DAC=/path`). Run `make probe`
or `make firmware-probe` to build the timed native or production-firmware/RTL
runner. The latter additionally requires Verilator.

```
python3 tools/check_runtime.py --binary build/classic-probe \
  --rom build/test.rom --backend native --suite all \
  --out local/fresh-ci-check --report reports/ci-runtime.json
```

For complete reference-ROM boot qualification, supply the external
`r1715bt.bin` identified in `NOTICE.md`; it is not redistributed. Replace the
binary with `build/firmware/classic-probe` and backend with `firmware` for the
shared production firmware/RTL path. Every output directory must be new.
Tests use private disk copies; source images remain unchanged.

The public fixture installs our resident platform services with ordinary Z80
instructions, then enters the same filesystem loader. It tests the guest OS,
controller and peripherals, but not the historical ROM descriptor or the
4000h first stage. Only external-ROM results cover those stages.

## Hardware and limits

A: only, fixed 800 KiB geometry, 2 KiB blocks, 128 directory entries and 20 KiB
reserved boot area. The console is 80×24 with CR/LF, backspace, tab, clear and
scrolling. The keyboard consumes E0/ASCII bytes through the motherboard SIO.
There is no bank switching, RTC, printer, auxiliary serial service or W-style
controller emulation. Unsupported drives are rejected.

Disk writes use 1024-byte read/modify/write with a clean read cache, no deferred
BIOS write-back. Successful controller transfer is **not a promise of SD
power-loss durability**. The carrier backup supply is not integrated here.
Raw-image field timing is not physical rotational or electrical qualification.
The simulator does not render the actual CRT or model serial waveforms.

Before physical use: qualify the board and connector independently, measure PIO
handshake/seek timing, verify keyboard clocking and video setup on the actual
mainboard, then repeat boot, utilities, protection, reset and persistence tests
on disposable media. No physical execution or production readiness is claimed.

New sources are MIT; adapted Juku sources are BSD-2-Clause. CP/M and build tools
retain their separate terms; see `NOTICE.md`. `python3 tools/package.py` produces
a deterministic simulator package with hashes and qualification reports.

The normal build assembles the 1715 BIOS and platform services and generates
CPM3.SYS with DRI tools. It consumes pinned upstream `BDOS3.SPR` and `CCP.COM`
inputs, as the Juku baseline does; the matching upstream source archive is
included. It does not independently rebuild every DRI kernel/utility module.
