# CP/M Plus 3.1 for Robotron 1715

Native, nonbanked CP/M Plus for the ordinary 64 KB Robotron 1715, using the
classic PIO floppy-controller interface. This is a new OS port, not a patched
1715W disk. The BIOS and bootstrap execute on the emulated Z80; no host service
intercepts BDOS calls or injects disk records into guest RAM.

The [1715M/W4 banked profile](docs/wm-banked.md) adds banked CP/M, at least
47 KiB of advertised TPA, and a 96 KiB volatile B: RAM disk. It is the W4
launcher default; `--nonbanked` retains the previous system.

A separate [serial build](https://github.com/ddanila/cpm-plus-1715/blob/main/docs/serial-console.md) adds stock-ROM V.24 boot,
a mirrored N4 remote console and host-backed A: using shared Juku protocol code.
The [unattended hardware runner](https://github.com/ddanila/cpm-plus-1715/blob/main/docs/unattended-serial.md)
executes one serial-only campaign after one manual power-on.

## Build

On Debian/Ubuntu install `build-essential bison python3 python3-pexpect`.
Run `git submodule update --init --recursive`, then `make all test`.
The pinned DRI tools run under a locally built ZXCC; zmac
is also built from source. No sibling Juku checkout is required.

Outputs:

- `out/cpm-plus-1715.img`: fresh 80×2×5×1024 raw A: disk.
- `build/cpm3.sys`: generated nonbanked system.
- `build/system-map.json`: resident map and system checksum.
- `build/test.rom`: original CI fixture, **not a replacement hardware ROM**.
- `build/keyboard-map.json`: resident queue and diagnostic addresses.

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
shared production firmware/RTL path. Each invocation creates a unique run
directory beneath `--out` and saves stdout/stderr there. `--report` is an
atomically published summary; failed runs do not publish a passing summary.
Tests use private disk copies; source images remain unchanged.

The public fixture installs our resident platform services with ordinary Z80
instructions, then enters the same filesystem loader. It tests the guest OS,
controller and peripherals, but not the historical ROM descriptor or the
4000h first stage. Only external-ROM results cover those stages.

## Hardware and limits

A: only, fixed 800 KiB geometry, 2 KiB blocks, 128 directory entries and 20 KiB
reserved boot area. The console is 80×24 with CR/LF, backspace, tab, clear and
scrolling. The keyboard consumes E0/ASCII bytes through the motherboard SIO, with a
128-character queue serviced during disk activity. See [keyboard behavior and
qualification limits](docs/keyboard.md).
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

Core new sources are MIT; adapted Juku sources are BSD-2-Clause. The cpmbox
adaptations use GPLv3-or-later. CP/M and build tools retain their separate
terms; see `NOTICE.md`.

## Disk tools and packages

See [disk tools](docs/disk-tools.md) for checked list, import, extraction and
validation commands. Imports always write a separate image; system files are
rebuilt through `make`.

```sh
python3 tools/check_reproducible.py
python3 tools/package.py --report reports/public-runtime.json --report reports/reproducible.json
```

The packaging command requires current source/output fingerprints, complete
passing runtime cases, and fresh-build reproducibility evidence. It never picks
up reports implicitly. To produce a release-qualified simulator package, also
supply `--release --report reports/native-runtime.json --report reports/firmware-runtime.json`.
Those two reports must cover the full suite with the reference ROM. CI packages
carry the narrower `ci` qualification label. Both remain simulation-only.
See [qualification](docs/qualification.md) for coverage and limits.

The normal build assembles the 1715 BIOS and platform services and generates
CPM3.SYS with DRI tools. It consumes pinned upstream `BDOS3.SPR` and `CCP.COM`
inputs, as the Juku baseline does; the matching upstream source archive is
included. It does not independently rebuild every DRI kernel/utility module.

The image also includes [P1715TST guest diagnostics](docs/diagnostics.md) for
patterned storage checks and cold-boot verification, using portable CP/M BDOS.

For persistent daily use, see [managed serial sessions](docs/managed-session.md):
one-command boot, detachable console and offline snapshots.

The default serial image includes [PIPEMGR and nine cpmbox utilities](docs/pipes-and-tools.md),
with text/binary pipelines and an explicit offline upgrade for existing sessions.

The **1715W/M serial-only target** is documented in
[W/M serial CP/M](docs/wm-serial.md). It uses a 1200 8N1 host console and
host-served A: disk, with an installed-W2 compatibility shim or the new W3
ROM. Build it with `make wm`. Physical CP/M qualification is pending;
this target has separate emulator evidence and CI packages.

### Experimental PC001 fast serial link (2026-11-11)

On the physical 1715M/W with W2 ROM, 41600 baud x16 booted CP/M Plus,
ran DIR and TYPE, and copied the 3200-byte CCP twice using PIP. Both saved
copies independently matched the original SHA-256. This is a short hardware
smoke test, not sustained reliability qualification. The preceding 62400
CP/M attempt exhausted disk-read retries despite passing a simple RAM echo.

`make wm-fast` builds a matched experimental platform/image using A5 counter
control 47h, constant 3 and SIO WR4 44h. `tools/serial_wm_fast.py` uses the
PL2303HXD USB divisor override on macOS and passes the configured descriptor
to the native host. It requires the verified W2 monitor already at 9600 x16
(or 41600 x16); the installed cold W2 starts at unreliable 9600 x1 and must
first receive a verified RAM clock shim. Do not use this launcher directly
after cold start. Monitor uploads are paced at 0.5 ms per byte; runtime disk
traffic is unpaced. The adapter runs approximately 41666 baud (+0.16%).

The fast build is experimental and separate from the default 1200 build.
Current emulator CI does not model this external counter clock. Reset after
a failed CP/M bootstrap did not restore a responsive ROM; power cycling did.
No ROM reburn or physical hardware changes were needed.

### Table CRC and 62400 experiment

`make wm-62400` builds a separate 62400 x16 platform/image (A5 counter 47h,
constant 2); `wm-fast` retains the 41600 fallback (constant 3). Both opt into
the Z80 table CRC. Two consecutive aligned 256-byte pages remove bit-loop
branches, index multiplication and BC saves. The CRC update takes 72 clocks
independent of input, compared with 462–702 clocks for the portable bitwise
routine (about 582 on typical data). The 512-byte table plus alignment changes
the boot payload from 3219 to 3858 bytes including its disk copy stub.

`tests/serial_crc_fast_test.py` runs actual assembled code on the DAC Z80 core
for all 16,777,216 CRC-state/input-byte combinations, checks an independent
bitwise reference, register preservation and a cycle bound. Set `DAC` to the
DAC source directory if it is not a sibling checkout. The normal 8080 and
non-fast Robotron paths retain their existing implementation.

Use `tools/serial_wm_fast.py --baud 62400` with the same boot/attach arguments
as 41600. Artifacts default to the matching baud and the launcher validates
the clock initializer. The installed W2 still requires the separate cold-start
clock recovery; this change improves uploaded CP/M, not the burned ROM.

Physical PC001 validation with this build: CP/M boot, three independently
verified 25600-byte binary files (original plus two generations of PIP copies),
warm boot and TYPE succeeded at 62400 with unpaced runtime traffic. The
197-second session logged 1269 record reads, 624 writes and zero retries.
The CRC change was sufficient to resolve the previous 62400 boot failure;
this supports processing overhead as the cause, although target UART overrun
was not separately instrumented. Longer soak testing remains useful.

### W4 ROM cold-start launcher

Firmware 4.0.0 / W4 discovers the host at 62400, 41600 or 9600 without a RAM
clock shim. Build matched images with `make wm-62400 wm-fast wm-9600`.
Use `tools/serial_wm_w4.py boot` with `--serial`, `--session`, `--console-pty`
and `--host` as for the previous launcher; `--baud` defaults to 62400 and can
select 41600 or 9600. It prints and records the ROM version, fingerprint,
integrity and rate before an unpaced upload/readback and exact STARTED handoff.
`attach` reuses the recorded disk and rate without probing a running CP/M.
The previous W2 launcher remains available for the installed ROM.

The W4 ROM is supplied by ravi as `src/ravi/backends/robotron1715w/rom-w4.bin`.
It must actually be burned before using this cold-start launcher on PC001.
The physical 30-minute soak and 20 cold starts are pending that installation.
`tools/check_w4_runtime.py` performs an actual-ROM CP/M boot, binary copy and
warm boot in the timed emulator at each rate. Its private PTY is a 9600 transport
bridge; the model independently generates the selected 9600/41600/62400 wire
clock. This is not evidence of the macOS USB driver's custom-rate behavior.

## W/M firmware 4.1.0 candidate

The [versioned 2 KiB ROM and checksums](firmware/w4-4.1.0/README.md) are included
for burning from another machine. W4 protocol compatibility is retained; idle
connections now expire back to baud scanning. Emulator ROM and banked CP/M
recovery tests pass. Physical qualification of this new image is pending.
