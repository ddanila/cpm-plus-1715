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
