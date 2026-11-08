# One-power-on serial hardware campaign

This runs one unattended campaign after a single manual power-on. It uses the
Robotron serial platform and **host-backed A: only**, at 9600 baud, 8 data bits,
odd parity and 2 stop bits. There are no physical floppy operations, formatting,
or controller tests. Leave physical drives empty: the stock ROM may probe their
interface before falling through to its V.24 loader.

PC002/MB003 passed all 11 supported groups on real hardware on 2026-11-08 in
17m 14s, using implementation commit `f003c87`. The campaign verified serial boot,
console/file operations, host restart, warm boot, deliberate CRC-fault recovery,
disk-full recovery and read-only protection. All five host sessions reported zero
UART errors; the only retry was the injected fault. The source image was unchanged.
[Raw captures, result and pinned provenance](https://github.com/ddanila/vintage-computer-inventory/tree/ccf6bb314391355b701e130e13161664eda866ec/items/MB003-robotron-pc1715/evidence/20261108-cpm-serial)
record the run, including its 300-second boot timeout. Local keyboard/video,
physical floppy operation and physical reset/power-loss recovery remain unqualified.
The host stopped after testing; the board was left powered at the CP/M prompt.

## Prepare and start

Use the revisions pinned in `dependencies.json`, with the sibling Ravi and
8080-cosim checkouts. Build on Linux:

```sh
git submodule update --init --recursive
make serial test
../8080-cosim/sync/jukuhost_linux_build.sh
```

Start with MB003 **off**, its RS-232 adapter connected and no other application
using that port. Run:

```sh
python3 tools/check_serial_hardware.py \
  --serial /dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0 \
  --board MB003 --out local/MB003-serial-001
```

When it prints **“Listening at 9600 8O2. Power on now”**, power on once. There
are no subsequent prompts, terminal setup steps or disk swaps. Choose a fresh
output directory for every attempt. The runner supplies the console PTY and
keeps the same exclusively owned serial descriptor across host restarts.

The defaults are a 120-second boot deadline and 60-minute overall deadline.
`--boot-timeout` and `--timeout` accept finite positive seconds. Ordinary
commands have 180-second deadlines, pattern operations up to 600 seconds and
the disk-full workload up to 900 seconds, always bounded by the overall limit.
This is a single pass, not an indefinite soak. The first complete emulator-backed
campaign took about 22 minutes at the modeled serial speed; physical timing
may differ.

## What runs

1. Stock-ROM bootstrap, exact monitor/platform readback, and CP/M prompt.
2. DIR, TYPE, backspace editing, PIP copy, RENAME and SUBMIT.
3. A 32 KiB patterned write, independent image inspection and collision handling.
4. Host restart while CP/M remains running, then file verification.
5. CP/M warm boot and persistence verification.
6. One deliberately corrupted read-reply CRC, matching duplicate/retry evidence,
   and correct resulting file contents.
7. Scratch-file cleanup and baseline integrity.
8. Disk-full handling, independent verification of the partial file, deletion,
   a fresh successful write/read cycle, and baseline integrity again.
9. Host restart in read-only mode, rejected write and an unchanged image hash.

Before touching the port, the runner creates a private `disk.img`, installs the
existing BDOS workload and adds deterministic filler files leaving 96 KiB free.
This bounds the disk-full test duration at 9600 baud. Every later filesystem
change is made by CP/M over serial. The original image is never modified or
served writable, and mounted media are never replaced or edited externally.
Classic/floppy-backed platform artifacts are rejected before device access.

Read-only transitions occur at a confirmed command prompt after stopping the
previous host and checking that no pending journal remains. The final host is
stopped when testing completes; the board stays powered. No further CP/M disk
access is possible until a compatible host is attached or a new campaign is
started after a manual power cycle.

## Results and failure behavior

`result.json` is atomically checkpointed after each stage. It records board and
port identity, artifact hashes, host invocations and read-only policy, elapsed
time, per-stage status, unsupported coverage and source-image integrity. The
folder also retains bootstrap bytes, readback, console output, host logs,
runtime captures, the working image and any pending crash journal.

Exit 0 means every supported stage passed. Exit 1 means failure, exit 2 means
invalid setup/arguments, and exit 130 means interruption. Unsupported tests are
listed explicitly and never counted as passes: physical reset/power loss,
local keyboard/video, floppy hardware, and alternate boot-image rejection.
A warm boot is not a physical reset.

On timeout, bad readback, unexpected host exit, disconnect, integrity failure or
interruption, testing stops. Only campaign-owned processes are terminated;
evidence and the working image are retained. There is no automatic LOAD/EXEC
replay, power cycle, repair of an uncertain journal, or retry of destructive
commands. A failed boot or unresponsive guest needs a manual power cycle before
a fresh campaign. Visible existing port owners and duplicate campaign/session
ownership are rejected rather than stopped.

## Reproduce the preparation checks

```sh
make serial-probe PICO=/path/to/pinned/Pico1715 DAC=/path/to/pinned/dac-emulation
python3 tools/check_hardware_runner.py --rom build/serial-test.rom \
  --out local/hardware-runner-check
```

That wrapper supplies a timed emulator serial endpoint **without any reset,
keyboard or fault-injection control descriptor**. All test operations use the
same physical-runner code and native host. Its `--scenario boot-timeout`,
`--scenario disconnect`, and `--scenario interrupt` modes exercise failure
capture. Use the external reference ROM identified in NOTICE.md for the full
stock-ROM path. No physical adapter is opened by these qualification commands.

The native host's opt-in `--test-corrupt-read-reply-once` flag is restricted to
the Robotron runtime profile and leaves its cached valid reply intact. Default
Juku and Robotron host operation never injects faults. Unit checks cover failed
readback/GO handoff, stale or absent prompts, duplicate ownership and journal
refusal; existing emulator and Juku integration suites remain in the gates.

## Saved qualification

`reports/hardware-campaign-public.json` and `hardware-campaign-reference.json`
record all 11 hardware-style groups passing through the public fixture and
historical ROM respectively. Both are emulator executions, not MB003 results.
`hardware-campaign-failures.json` records successful timeout, interruption and
disconnect checks, with the inner campaigns correctly marked failed/interrupted.

The two `hardware-emulator-*.json` reports retain all 24 existing serial checks.
The classic native suite passed 43 cases and the firmware smoke suite passed
three; their reports match the final source manifest. `reproducible.json` and
`hardware-software-validation.json` record unchanged/reproducible outputs, Juku
compatibility, native-host integration and Ravi transport/Robotron checks.
