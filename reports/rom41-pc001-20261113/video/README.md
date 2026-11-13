# PC001 video adapter digital qualification — 2026-11-13

PC001 passed a serial-controlled, RAM-loaded diagnostic with video adapter and
FDU installed, no external monitor/keyboard, ROM W4 4.1.0 and banked CP/M at
62400. No power cycle, reset button, ROM change, or floppy access was needed.

The first test exposed an emulator error: the CPU window `3000–3fff` is **2 KiB
of screen RAM mirrored twice**, not independent 4 KiB. Expected `50` at `3000`
read back `58`, the pattern written at `3800`; the inverse pattern similarly
read `A7` instead of `AF`. This was repeatable, not random corruption.
The revised test checked every byte in both aliases, writing in both directions,
with two complementary address-dependent patterns. Both final runs passed.
Character RAM `2000–2fff` passed as independent 4096 bytes. All original character
and screen contents were saved and restored, with exact readback verification.

Original schematic 1.93.310412.6/04, sheets A/B (`Stromlauf CRT-Steuerung`) in
[1715w.zip](https://xepb.org/robotron/docs/1715w.zip) corroborates the measurement:
screen D03 is a single U6516 with A0–A10; character memory D08/D09 uses two.
[MAME rt1715.cpp](https://github.com/mamedev/mame/blob/master/src/mame/robotron/rt1715.cpp)
uses a 0xfff video index; that implementation was not treated as hardware evidence.

8275 status was **04 / 00 / 04** before stop, after stop, and after restart with
interrupts disabled. Geometry and cursor parameters were not reprogrammed.
Status reads acknowledge sticky flags; stopping/restarting changes raster phase.
The test does not preserve those transient states or validate sync/analogue output.

Afterward, TYPE HELLO.TXT worked, a file was copied to/read from/removed from RAM
disk B:, and every pre-existing file on host-backed A: matched its original bytes.
CP/M and the automatic serial host were left running at A>. VIDTEST.COM remains
on the private session disk, not the distributed system image.

## Reproduce

`make test-video` assembles [src/video-test.asm](../../../src/video-test.asm) and
runs its real Z80 instructions in the corrected DAC emulator. The probe tests
success, injected readback corruption with successful restoration, an unsupported
platform rejection, and untouched non-application banks/common scratch.
`make test-banked` also passes. DAC `test-robotron-devices` includes a regression
which fails with the old decode; it and the 20 physical bank-bus cases pass.
DAC fix: `8e559628`; the dependency pin includes it.

The COM is intentionally bound to this qualified banked 62400 platform's first
32 jump-table bytes and an initial controller VE=1/IE=0 state. This is a narrow
compatibility guard, not a full ROM/platform identity check. It assumes the
W4 display start configuration, DI execution, application selector 2, available
4000–9fff TPA scratch, and unused common F700 scratch (saved/restored). Do not
use it with an unrelated CP/M build or a future local-console driver without
reviewing those assumptions. `build/video-test.cim` is the CP/M COM payload.

[Initial mismatch](initial-4k-assumption.txt), [full session excerpt](console.txt),
and [machine-readable result / payload SHA-256](result.json).

This qualifies memory decoding, writable/readable RAM and controller status.
It does not prove displayed pixels, monitor compatibility, keyboard operation,
physical floppy readiness, display refresh timing, or a local CP/M console.
