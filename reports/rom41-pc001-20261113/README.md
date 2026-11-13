# ROM 4.1.0 and banked CP/M on PC001 — 2026-11-13

Owner installed ROM 4.1 and powered on PC001, the Robotron 1715M. The host
identified W4 firmware **4.1.0**, build **5d0209bb55b89711**, with a passing
whole-ROM CRC check. No reset or further power cycle was required.

## Physical results

- Initial discovery at 62400, using the qualified macOS PL2303HXD custom
  divisor path (adapter calculates 62500, +0.16%).
- After 12 seconds idle each time, changed to 41600, then 9600, then 62400;
  identified the ROM afresh and wrote/read/compared 2048 bytes of RAM at E000h
  at each speed. No explicit release command or target reset was sent. This
  directly exercises 4.1's idle expiry back to baud scanning.
- Automatic host detected the ROM, uploaded and verified the banked platform,
  and booted CP/M Plus to A> in 19.35 seconds from host launch.
- Advertised TPA memory test passed. B: full directory, full disk, random record
  and allocation reuse tests passed.
- B: contents survived three warm boots, plus the warm boot during the large
  file round trip.
- An 81920-byte binary A: → B: → A: transfer matched independently after clean
  host shutdown. SHA-256:
  `423b90ec6b7d291d678c3e7ddc1a6e98830adaab82bf5572de675c015a0a851e`.
- Restarting the same automatic host reattached to running CP/M and verified
  HELLO.TXT from both A: and B:, preserving the session.
- Closed successful session: 1757 record reads, 660 writes, **zero retries and
  zero UART errors**. Original source disk unchanged; private test image used.

The host and machine were left running at A>, at 62400. B: is volatile and
will not survive a fresh OS boot or loss of power.

## Scope and setup correction

This is one physical cold start and a short functional qualification, not a
repeated cold-start or long-soak reliability campaign. Running-CP/M physical
reset/power-cycle recovery, local video/keyboard, physical floppy drives, and
absent/faulty RAM were not tested. The new ROM's broader emulator evidence
remains in the firmware directory.

The first host-launch attempt failed before serial traffic because the
isolated artifact directory lacked its `tools/recovery_profile.py` path.
Adding a link to the repository tools corrected the harness; subsequent
boot and reconnect passed without touching the hardware. The failed attempt's
log is retained separately and is not counted as a target failure.

`rom-tests.json`, `cpm-tests.json`, console and host logs preserve the results.
The `.py.txt` files preserve the bench harness used; they are evidence, not
standalone supported launchers. The preparation script required the tools
symlink described above. The actual shared-host checkout used was newer than
this repository's pin; its revision and executable hash are recorded explicitly.

## Follow-up 10-minute soak

The same powered-on PC001 passed a **638.02-second** soak at 62400 without any
operator intervention. Eight 80 KiB A:→B:→A: rounds returned **655360 bytes
(640 KiB), all exact matches**, independently inspected after clean host stops.
Each round included a warm boot and an automatic host reconnect; B: retained
its files throughout. Round three held the host disconnected for 45 seconds.

Eight closed host epochs totalled 8272 record reads and 5320 writes with
**zero retries, zero UART errors and zero target resets**. A:→B: times were
35.39–35.55 seconds, B:→A: 30.74–30.81 seconds, and reconnection plus both-disk
checks took 2.41–2.76 seconds. No progressive slowdown was observed. These are
end-to-end CP/M file-copy times, including protocol/filesystem overhead.

The final automatic host was left running; a post-soak TYPE HELLO.TXT
confirmed the console remained at A>. The source disk remained unchanged.
This extends the initial functional campaign; repeated physical cold starts
and reset/power-cycle recovery are still outside this session's coverage.
[Results and counters](soak-10min/result.json),
[console](soak-10min/console.txt), and closed host logs are preserved alongside
the bench script. Only the disposable BIG.BIN/BACK.BIN destinations were
replaced; no user disk or physical floppy was used.

## Physical power-cycle recovery

Following the soak, the owner switched PC001 off and back on with the serial
cable connected and the automatic host still running. The same launcher
process and native-host log epoch remained active. The host detected missing
runtime traffic, rediscovered W4 **4.1.0 / 5d0209bb55b89711** with passing ROM
CRC, uploaded/read-verified the platform and automatically booted banked CP/M
at 62400 to A>. No host restart or manual upload was needed.

TYPE HELLO.TXT succeeded on A:. The complete 819200-byte host disk was identical
to the pre-cycle snapshot, including the exact 81920-byte BACK.BIN test file.
DIR B: reported `No File` and SHOW reported 94 KiB free: the volatile RAM disk
was freshly initialized as expected. CP/M and the host were left running at A>.

[Result](power-cycle/result.json), [console](power-cycle/console.txt),
[ROM recovery identity](power-cycle/recovery-booted.json), and a live host-log
snapshot preserve this check. This supersedes the earlier power-cycle coverage
limitation for a single physical cycle; repeated cold starts and RESET-only
recovery are still untested. Power-on timing was not instrumented. The log
snapshot is from the still-running host, so it has no final aggregate counters.

## Reassembled machine serial check

The owner reassembled PC001 with the video adapter and FDU installed, but no
external display or keyboard connected, and reconnected the serial cable.
After reopening `/dev/cu.usbserial-2110`, the automatic host discovered ROM
4.1.0 with the expected build and passing CRC at 62400, uploaded the platform,
and booted banked CP/M to A>. TYPE HELLO.TXT succeeded over serial, and the
host disk remained unchanged. CP/M and the host were left running.

[Results](reassembled/result.json), [console](reassembled/console.txt), and a
live host-log snapshot record this configuration. This confirms serial boot
and console operation with the boards installed; it does not qualify video
output, keyboard operation, or physical floppy I/O.
