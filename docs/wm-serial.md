# Robotron 1715W/M serial CP/M Plus

W4 now defaults to the [banked profile with RAM disk](wm-banked.md). Build
`make wm-banked` before using the W4 launcher. Pass `--nonbanked` for the
previous W4 image. The original W2/W3 profile below remains nonbanked.

This target uses the W/M mainboard, its V.24 serial port and one 64 KiB RAM
bank. The console and writable 800 KiB A: disk are served by the host.
No video board, local keyboard or floppy drives are required. The first
version runs at **1200 baud, 8 data bits, no parity, one stop bit** with
SIO x16 sampling. It uses the existing nonbanked CP/M Plus 3.1 BIOS and
shared Juku N3 disk/N4 console engines. Faster operation and banked CP/M
are outside this milestone.

## Build

The exact tested dependency revisions are in `tools/wm-dependencies.json`.
Check out those revisions of Ravi, dac-emulation and 8080-cosim alongside
this repository. Python 3.10 or newer, a C/C++ compiler, make and bison
are required. Install Ravi in your Python environment:

```
python3 -m venv build/venv
build/venv/bin/pip install -e ../ravi pexpect
make wm wm-probe PYTHON=build/venv/bin/python DAC=../dac-emulation
bash ../8080-cosim/sync/jukuhost_linux_build.sh
```

The outputs are `out/cpm-plus-1715-wm.img` and `build/platform-wm.cim`.
The platform loads at C000h, enters at C033h and sets bank port 24h to
11h. CP/M occupies 9D00h–BFFFh; the stack starts at F700h. No boot from
floppy is involved.

## ROM choices

* W3: `ravi/src/ravi/backends/robotron1715w/rom-w3.bin`, a 2048-byte
  2716 image. It starts directly at 1200 8N1, build ID
  `fa36fb508b27f4eb`, SHA-256
  `3d8aad7f65ca30266a12998fd31774d18ae172ea8fcbb6ccd28ad73f14e83591`.
* Installed W2: the launcher accepts only build ID `4f81c5516ba23bbc`.
  Start from a fresh reset at 9600 baud. It writes and reads back a
  27-byte RAM shim at 8000h, executes it once, then continues at 1200
  baud. No ROM change is needed. Bounded retries apply only to scratch
  writes and reads; an uncertain execute acknowledgement is never replayed.

W3 is emulator-qualified; it has not yet been tested on PC001. W2's clock
shim has previously been exercised on PC001. The first physical CP/M trial
verified the complete platform upload and execution acknowledgement, then
stalled on malformed runtime serial requests before reaching a prompt.
Hardware debugging is in progress; the complete CP/M session is not yet
qualified on PC001. This is not a Kaypro ROM.

## Run

Create a connected PTY pair for the console (for example with `socat`) and
attach a terminal to its other end. Use the explicitly selected RS-232
adapter and the terminal's actual PTY path:

```
build/venv/bin/python tools/serial_wm.py boot \
  --serial /dev/cu.YOUR_ADAPTER --rom-profile w2 \
  --session local/pc001-session --console-pty /dev/ttysYOUR_PTY \
  --host ../8080-cosim/build/jukuhost
```

Use `--rom-profile w3` for W3. If W2 is already running with the temporary
1200-baud clock correction from a prior monitor session, add `--w2-at-1200`
to `boot`; the launcher still checks its exact fingerprint and ROM integrity
before writing anything. This option skips the clock shim, not verification.
Expected output is the CP/M Plus banner
followed by `A>`. Try `DIR` and `TYPE HELLO.TXT`. The launcher verifies the
ROM identity and platform readback before execution. It keeps the serial
port open and exclusively owned while handing its descriptor to the disk
host. It copies the source image into the new session directory; writes
modify only that session's `disk.img`. `--read-only` rejects guest writes.

Stop the host with Ctrl-C. To reconnect to a still-running CP/M system,
repeat the command with `attach` instead of `boot`, keeping the same
session, ROM profile, artifacts and read-only setting. Do not reset the
target for attach. If you reset the target, use `boot` with a new session.
The launcher rejects mismatched session identities. Preserve the entire
session, including any journal, after an interrupted write.

For the downloadable package, install the pinned Ravi version and pass
`--image cpm-plus-1715-wm.img --platform platform-wm.cim --host ./jukuhost`.
The native host executable must match your operating system.

## Qualification

`tools/check_wm_runtime.py` boots the actual ROM in the W/M device model,
uploads the platform using the production launcher, and runs real CP/M
commands. It checks text/binary copies through an independent disk parser,
rename, erase, warm boot, host restart, source-image preservation, read-only
media and optional corrupt disk-reply recovery. No physical adapter is
opened by this test. CI runs on Linux and macOS with pinned dependencies.

The model uses a synthetic equivalent CAS PROM, not a dump from PC001.
Video and keyboard are disconnected and no floppy media is installed.
The independent receiver test sweeps 416 clock phases with clock skew:
x16 passes all phases; x1 fails 176. Accelerated PTY tests explicitly skip
host wall-clock drain estimates because the emulated wire clocks each bit;
real serial descriptors still use the operating system's drain operation.
Evidence therefore does not substitute for a physical clock/contact test.

W3 uses 1760 of its 2046 payload bytes, leaving 286 bytes plus its two-byte
CRC. Reports and SHA-256 manifests are included in CI packages. Hardware
qualification remains a separate, coordinated step with PC001 powered and
connected deliberately.

## Automatic recovery

The current launcher also accepts `auto`: `serial_wm_w4.py auto` for W4,
or `serial_boot.py auto` for stock 1715. Keep the same session directory and
options. The shared host detects boot versus running CP/M and recovers after
a later target reset while preserving the private disk and journal. W4 keeps
the selected banked/nonbanked profile and rate. W2/W3 retain explicit workflows.

The pinned host's `host/python/jh_recovery` modules are required (packages put
them beside the executable under `python/`). Custom adapter configuration is
shared with Kaypro; PTY emulator runs never open USB devices. Stock-ROM partial
LOAD/EXEC cannot be replayed safely and ends with an intervention-required
error. Reset the machine before attempting recovery again.

Details: [shared recovery](https://github.com/ddanila/8080-cosim/blob/master/docs/serial-recovery.md).
