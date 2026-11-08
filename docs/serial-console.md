# Serial boot, N4 console and host-backed A:

The separate serial build uses the motherboard SIO-B at **9600 8O2**, without
hardware flow control. Local keyboard/video remain active, and console output
is mirrored through N4. Only A: is supported: a raw 800 KiB image, 160 logical
tracks of forty 128-byte records. The classic PIO disk build stays the default.

## Architecture

Ravi boots its RAM monitor through the stock ROM V.24 loader, verifies the
monitor and resident platform by readback, then starts C033h. The launcher
consumes exactly GO and transfers the same open descriptor to the native
`jukuhost` process. No close, input flush or READY wait occurs at that boundary.
The resident filesystem loader reads CPM3.SYS through NetDisk and verifies its
header and payload checksum before entering CP/M.

N4 and NetDisk-v3 assembly are included directly from the pinned juku-common
submodule. Robotron supplies bounded SIO byte hooks and BIOS glue; it does not
copy the protocol implementations. A portable CRC variant handles the Z80's
ADD overflow flag, which differs from the 8080 parity flag. The native host
reuses the existing N4 dispatcher, journal and console machinery with a
Robotron media/framing profile. One-record requests and cache invalidation
avoid carrying stale read cache across host reconnects.

## Build

Initialize the shared source and build the serial artifacts:

```sh
git submodule update --init --recursive
make serial test
```

Outputs are `out/cpm-plus-1715-serial.img`, `build/platform-serial.cim` and
`build/serial-test.rom`. The last is an original emulator fixture, not a
replacement motherboard ROM. Check out the sibling Ravi, 8080-cosim, DAC and
Pico1715 revisions listed in `dependencies.json`. Build the host with
`../8080-cosim/sync/jukuhost_linux_build.sh` (that script changes to its own
repository). Install Ravi's Python dependencies or use its configured venv.

For the single-power-on hardware campaign, see [unattended serial testing](unattended-serial.md).

## Boot and attach (Linux)

The terminal endpoint is a raw PTY supplied by your terminal frontend. With
`DEVICE` and `CONSOLE_PTY` set to the selected endpoints:

```sh
PYTHONPATH=../ravi/src python3 tools/serial_boot.py boot \
  --serial "$DEVICE" --console-pty "$CONSOLE_PTY" --session local/session-001
```

Start the launcher before cold booting the target. Each boot requires a new
session directory and copies the source image into `disk.img`; all writes and
the host journal belong to that private copy. `--read-only` rejects writes.
The session records source/platform/host hashes, verified platform readback,
bootstrap bytes, host logs and runtime captures. Do not run two hosts against
the same port or working image.

To restart the host while CP/M is still running, use the same image/platform
arguments and session:

```sh
PYTHONPATH=../ravi/src python3 tools/serial_boot.py attach \
  --serial "$DEVICE" --console-pty "$CONSOLE_PTY" --session local/session-001
```

Attach validates session identity and does not reset or upload to the guest.
For a later cold boot with saved files, use `boot --image
local/session-001/disk.img --session local/session-002`. Protocol retries are
bounded; an absent host can produce a disk error. An uncertain execution
handoff is never automatically replayed. A process restart is not a promise
of exactly-once writes across arbitrary crashes or physical power loss.

## Emulator qualification

```sh
make serial-probe PICO=/path/to/pinned/Pico1715 DAC=/path/to/pinned/dac-emulation
python3 tools/check_serial_runtime.py --rom build/serial-test.rom \
  --out local/serial-public
```

Use the externally supplied reference ROM identified in NOTICE.md as `--rom`
for the stock-ROM path. The harness creates PTYs, runs real Z80 code and timed
SIO transfers, and invokes the production Ravi/host path. It never opens a
physical serial device. Full runs cover utilities, editing, corrupted reply
recovery, patterned-file integrity, host restart, warm/cold boot, local keyboard
mirroring, cleanup, read-only media and disk-full handling. Results and raw
evidence remain under the requested output directory; failed runs record an
error and `complete: false`.

The reference-ROM fixture models four unreadable scratch drives so its disk
probes fall through to V.24. This does not qualify every diskless board wiring
configuration. SIO byte timing and finite buffering are modeled, but PTYs do
not validate electrical levels, parity waveforms, physical clock accuracy, or
MB003. No physical execution was performed for this implementation.

## Recorded checks

`reports/serial-public-runtime.json` and `reports/serial-reference-runtime.json`
record complete 24-check runs through both boot paths.
`reports/serial-classic-native.json` covers all 43 classic native cases, and
`reports/serial-classic-firmware-smoke.json` covers the three firmware smoke
cases with the final source manifest. Both serial runs used the final
host/platform/emulator binaries and observed the deliberately corrupted reply.
`reports/reproducible.json` records ten unchanged classic outputs plus three
reproducible serial outputs. The shared hook compatibility check preserved
Juku's legacy and C9 binaries byte for byte. Ravi's 18 Robotron tests, the Linux
host integration gate and DOS host checks also passed.

The optional Windows packaging check reached an existing recovery-payload hash
mismatch in the sibling Juku checkout after its configuration/platform tests
passed. No Windows Robotron profile or physical hardware qualification is
claimed. The Robotron launcher and runtime profile are qualified on Linux.

The earlier extended firmware run passed all 43 runtime cases, including reset
recovery, but its source-change guard refused manifest publication because
serial tooling and dependency metadata were finalized while it was running.
`reports/serial-extended-firmware.json` preserves that result and evidence hashes
as supplemental regression evidence, not release qualification. The fresh
firmware smoke report above matches the final sources.
