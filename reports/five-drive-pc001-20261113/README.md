# PC001 five-drive CP/M and first physical floppy qualification

2026-11-13, PC001 Robotron 1715M, W4 4.1.0, video adapter and FDU installed,
no monitor or local keyboard. Serial console stayed at 62400 requested
(PL2303 actual 62500), 8N1. The owner authorized erasure of the diskette in
first physical drive C:. No diskette was written in D:.

## Result

- A: serial system, B: persistent additional serial disk, C:/D: physical
  drives 0/1, E: 96 KiB volatile RAM disk.
- C: formatted as 80 cylinders × 2 heads × 5 sectors × 1024 bytes. All 800
  sectors read back as E5. Full format plus verification took 261.52 seconds.
- CP/M created and read HELLO.TXT on C:, then copied it to serial B:; host-side
  bytes matched the original. An 8192-byte patterned binary likewise survived
  A: → C: → B: byte for byte, crossing sector and track boundaries.
- The final SYS/platform was reloaded from RAM. Its first C: access succeeded
  without a manual PROBE, and a fresh C: → B: binary copy matched again.
- B: persisted through OS reload; E: was empty after reload. Video memory
  diagnostics passed with the five-drive build. No owner reset/power cycle
  was needed during this campaign.
- At completion physical writes were locked, motors stopped, and the serial
  host was left running at A>. This diskette is a data disk, not a boot disk.

See [hardware.json](hardware.json), [console.txt](console.txt) and
[artifact hashes](artifacts.json). The binary pattern hash is
`384121f3c086d2eec60e27816c1062d7bebf3b772a8881dfd610c9e9efaa95ab`.

## Findings and corrections

The first implementation used CPU-polled transfers. A motor/control sequence
inferred from the previous model timed out waiting for the first index. The
[S550 firmware and motherboard schematic archive](https://xepb.org/robotron/docs/1715w.zip)
show the working reset sequence 30h/70h, selected control E0h, motor values
11h/22h and off 00h. Control E1h produced overruns. With E0h the polled loop
verified two tracks before an overrun; its transfer timing was too marginal
on this specimen. This is evidence for replacing PIO, not a measurement of
every wait state or every control bit.

The driver now uses UA858 DMA, memory endpoint DC00h and fixed I/O endpoint
41h as in S550. DMA completion drives FDC terminal count. Full physical
format/readback and file round trips passed. Failed command setup disables
DMA; invalid positions, write protection and unavailable media return errors.
The initial successful format used the RAM-patched DMA candidate archived as
`format-driver.cim`. The final driver adds command-error cleanup and startup
recalibration; its complete format/RMW tests passed in the emulator and its
post-reload reads passed physically. A second full physical format was not
needed or performed for those corrections.

A RAM reload initially returned a C: disk error until explicit recalibration.
Resetting the controller does not mechanically home the head. First access
now recalibrates each unit before a relative seek; two bounded attempts cover
the 8272's 77-pulse limit on an 80-cylinder drive. The driver regression starts
with the physical head at cylinder 79 and the logical counter at zero. Exact
PCN retention on this specimen's reset remains unmeasured; the driver does not
rely on it. MAME's [765 reset implementation](https://github.com/mamedev/mame/blob/master/src/devices/machine/upd765.cpp)
also should not be taken as proof of this specimen's reset state.

DAC now models the low-nibble, active-high motor latch and the FDC's non-DMA
execution status bit. Regressions cover both. The BIOS unit fixture also now
stubs every serial-adapter vector: its earlier SETTRK/SETSEC fall-through
could execute stack bytes and corrupt the resident driver during a unit test.

## Verification and limits

- Full emulator formatter: all 160 tracks/800 sectors, E5 readback, second
  disk unchanged. Driver tests cover per-drive unlock, 128-byte read/merge/write,
  last head/cylinder, invalid positions, protected media, absent readiness,
  unknown initial head position and motor stop.
- BIOS banked I/O, RAM boundaries, TPA and video memory tests passed.
- Extended 62400 emulator runtime covers serial B:, RAM E:, 80 KiB cross-bank
  copy, cold RAM clearing, fragmented SYS and nonzero power-on RAM.
- Fresh source rebuild is byte-reproducible. CI runs these driver tests and
  the existing multi-rate runtime/recovery campaigns on Linux and macOS.

D: has only emulator coverage; its physical selection, media and mechanics
are not qualified by this run. Only native 800 KiB media is supported. No
local keyboard/display console, stock-ROM boot disk, arbitrary disk formats,
or long-term floppy reliability is claimed. The PIO failure also shows that
emulator transfer timing alone is insufficient physical qualification.

`src/floppy-check.asm` and `src/wm-reboot.asm` are bench tools for the matched
five-drive layout. They are not installed in distributed images. The former
replaces the resident D000h driver; the latter embeds the current 62400
platform and requires its matching CPM3.SYS already on A:. Ordinary users
should use the launcher and the image's FORMAT.COM.
