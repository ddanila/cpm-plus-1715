# Everyday serial CP/M sessions

The Linux managed launcher owns the serial port and runs the native disk host in
background. Closing or detaching the console leaves A: available to CP/M. Only
host-backed serial media are used. Leave physical floppy drives empty; the stock
ROM may probe their interface before entering its V.24 loader.

Build `make serial test` and `../8080-cosim/sync/jukuhost_linux_build.sh` using the
revisions in dependencies.json. No pip package, terminal program or system service
installation is needed; the launcher loads Ravi from the sibling source checkout.

## First boot and daily use

With the machine initially off:

```sh
python3 tools/cpm_session.py boot --session local/my1715 \
  --serial /dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0
```

Power on after the launcher says it is waiting. The command starts the background
supervisor, verifies the uploaded monitor/platform and attaches its own terminal
after CP/M reaches A>. The boot deadline is 120 seconds; `--boot-timeout SECONDS`
changes it. There is no lifetime limit after startup. `--detach` starts service
without attaching the terminal. Startup failures are printed and retained in logs.

Use Ctrl-] followed by `d` to detach. Double Ctrl-] sends a literal Ctrl-]; Ctrl-C
is passed to CP/M. Reconnect or inspect service without rebooting:

```sh
python3 tools/cpm_session.py attach --session local/my1715
python3 tools/cpm_session.py status --session local/my1715
python3 tools/cpm_session.py status --session local/my1715 --json
```

One terminal can attach at a time. Each attachment shows up to 64 KiB of previous
output from the current host invocation, then live output. Detached output is
continuously logged. A slow client is disconnected before its output queue can
block the disk host. Terminal modes are restored on normal detach, EOF, Ctrl-C
received as a host signal, SIGTERM and SIGHUP; SIGKILL cannot run cleanup.

To stop service, first return CP/M to its command prompt, then detach and run:

```sh
python3 tools/cpm_session.py stop --session local/my1715
python3 tools/cpm_session.py resume --session local/my1715
```

`resume` is only for the **same still-running guest**. It does not send bootstrap
commands, reset CP/M, or replace media. After a physical power cycle use `boot`
with the same session; it reuses disk.img, including all saved files. The launcher
cannot identify a physical power cycle automatically. Never send `boot` into an
already-running CP/M. Stopping disk service does not turn off the machine.

The first boot records serial, source image, platform, host, read-only mode and
emulator mode. Optional `--image`, `--platform`, `--host` and `--read-only` apply
to initialization; subsequent commands use this configuration and verify artifact
hashes. No automatic upgrades, legacy-directory migration, bootstrap replay or
host restart occurs. The existing serial_boot.py interface remains available for
old low-level sessions. Use a fresh, short session path for the managed format.

## Offline snapshots

After stopping service at a CP/M prompt:

```sh
python3 tools/cpm_session.py snapshot --session local/my1715 --name before-work
python3 tools/cpm_session.py restore --session local/my1715 --name before-work
```

Snapshots cannot be overwritten. Both commands refuse an active session or pending
crash journal. Restore checks the snapshot hash and compatibility, retains the
current image as `snapshots/rollback-<id>`, and atomically replaces disk.img.
**After restore, power-cycle the guest and use boot.** Resume is blocked because
the guest may retain cached filesystem data from the previous image.

Do not externally edit or replace mounted media. An interrupted write may leave a
`.jhj` journal; the launcher preserves it and refuses automatic repair. Inspect
logs before recovery. Snapshot consistency assumes the guest reached a prompt
before the service stopped; stopping is not an automatic guest filesystem flush.

## State and failure evidence

Each session has private permissions, an exclusive lock, identity.json, status.json,
a local control socket, persistent disk.img, snapshots and per-invocation runs.
Each run preserves supervisor/host logs, raw wire capture, console output and a
result record; boot runs additionally retain bootstrap bytes and exact readbacks.
These logs grow with use and are not automatically pruned.

Status verifies the live control endpoint and lock rather than trusting a PID.
A dead host stops its supervisor; a dead supervisor signals its host to exit,
including when the supervisor receives SIGKILL. A PTY retains its exclusive flag
while its emulator master remains open after SIGKILL; restart the emulator with a
fresh PTY before booting again in that case. Failures preserve media/evidence.
Only owned children are stopped. Terminal detachment never stops the host.
Service stop is also available during bootstrap; an interrupted boot requires a
fresh guest boot, not resume. CLI success is exit 0, failure 1, argparse errors 2,
and console interruption 130.

## Emulator qualification

No hardware is accessed by these commands. Build the timed emulator with the
pinned Pico1715/DAC sources, then use fresh output directories:

```sh
make serial-probe PICO=/path/to/Pico1715 DAC=/path/to/dac-emulation
python3 tools/check_managed_session.py --rom build/serial-test.rom --out local/managed-check
python3 tools/check_managed_session.py --rom build/serial-test.rom \
  --suite failures --out local/managed-failure-check
```

The lifecycle uses the real CLI, supervisor, terminal and native host. It checks
background writes, reconnect, persistence, snapshot/restore with cold boot,
read-only storage and refusal boundaries. Fault checks cover bootstrap timeout,
startup stop, host death, supervisor termination and serial disconnect. Emulator
reset is used only for explicitly fresh boots; no physical reset control exists.
The historical reference ROM identified in NOTICE.md can replace the public ROM
for the same checks. Reports explicitly say `hardware_executed: false`.

### Recorded qualification

The 2026-11-09 emulator-only qualification passed all nine lifecycle groups with
both the [public fixture](../reports/managed-session-public.json) and
[historical reference ROM](../reports/managed-session-reference.json), plus all
six [failure groups](../reports/managed-session-failures.json). Each lifecycle
used the production CLI and native host, with four clean host exits and zero UART
errors. All 42 unit tests passed; the fresh-source build reproduced all 13 outputs,
byte-identical to the previous hardware-qualified classic and serial firmware.

The [qualification summary](../reports/managed-session-qualification.json)
collects regression outcomes and hashes of retained evidence. Raw local captures
remain under the recorded run paths; CI uploads its public-ROM captures as
artifacts. This qualifies the new managed launcher in the emulator only. The
older physical MB003 results in unattended-serial.md do not constitute hardware
execution of this new launcher.

For PIPEMGR/cpmbox installation and rollback, see [pipes and tools](pipes-and-tools.md#existing-managed-sessions). New sessions retain source inputs by hash; rebuilding the default image does not change existing session disks.
