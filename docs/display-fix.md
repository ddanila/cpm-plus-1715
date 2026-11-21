# Ordinary PC1715 blank display — 2026-11-21

The owner reported a blank physical display on PC002 while our CP/M Plus 3.1
serial console worked. This investigation used emulators only. It found a
sufficient software cause and fixed it; physical validation remains pending.

## CP/M cause and reproduction

Both ordinary-PC1715 platform builds initialized their F800h character buffer
but never reset/configured/started the 8275 or selected that buffer in the
hardware latch. They relied on inherited video state. Earlier runtime tests
inspected screen RAM or serial text, with the video device disabled, so they
could pass while no raster was generated.

Executing the old initialization and local console instructions on the corrected
DAC model reproduces the failure in both builds: RAM contains the banner,
while the controller is stopped, fetch count is zero and all pixels are black.
The serial binary's SHA-256 matches the platform previously used on hardware:
`09546a8ab354d0c5578cf4f87689046b1247dbd5bc428c5e7c633ab1fd9d9174`.

The fixed platform resets the 8275, programs the K7222.25 80×24 configuration
(4F/57/6B/6D), selects F800h with `OUT (34h),3Eh`, loads the cursor and starts
scanout. Local output updates the cursor after editing, wrapping and scrolling.
The ordinary classic and serial builds share this code; W/M initialization is
excluded by `WM_BOOT`.

The fast regression executes those production routines, checks every pixel
against independent glyph data, and covers dirty latch state, cursor position,
CR/LF, tab, backspace, wrapping, scrolling and clearing. Old and fixed results
are preserved in [plain-video-regression.json](../reports/plain-video-regression.json).
Synthetic glyphs deliberately distinguish bank, character and scanline; they
are not a historical font dump or evidence of physical glyph-ROM contents.

## Shared diagnostic-ROM/emulator mistakes

The [service manual I/O table and display sections](https://www.sax.de/~zander/pc1715/doku/pc_serv.pdf)
and [ZRE schematic sheet 2](https://www.sax.de/~zander/pc1715/pc_zres.pdf) establish:

- 18h/1Ah are CRT parameters; 19h/1Bh are CRT commands/status.
- 34h–37h select the screen/glyph latch. 20h–23h control the floppy interface.
- A23.2 D1–D5 drive AB11–AB15 via A22.4. X12 selects counter AB10 for
  80-column operation. D0 is not part of this mode's 2 KiB block selection.
- D6 XOR GPA0 selects the glyph bank. F800h therefore requires latch value 3Eh.

The initial DAC video model and RAVI CRT 1.0 ROM shared **both** wrong assumptions:
port 22h and D0–D4 block selection. Their mutual agreement made the old emulator
qualification misleading. DAC now uses the documented decode/wiring, tests all
32 blocks and latch aliases, and checks that floppy I/O still reaches the card
and its WAIT callback with video enabled.

[RAVI CRT 1.1](https://github.com/ddanila/ravi/tree/main/firmware/robotron1715-crt)
fixes both errors and rebuilds every cycle/fixed boot image. Full qualification
includes deliberately misassembled old-port and old-bit-mapping variants; both
must fail the independent raster comparison. Two complete cycles, all fixed
patterns and RAM-fault/reset cases pass on the corrected model.

Only A25.3 needs reprogramming for the CRT kit. Both glyph ROMs are byte-identical
to 1.0. An earlier successful electrical burn of A25.3 1.0 verified the wrong
firmware image; it did not qualify its display behavior. No EPROM was burned or
physical serial connection opened during this fix.

## Repeatable checks

Use the DAC revision pinned in `dependencies.json` and the normal build tools:

```
make all serial test
make test-plain-video DAC=/path/to/pinned/dac-emulation
make serial-probe PICO=/path/to/pinned/Pico1715 DAC=/path/to/pinned/dac-emulation
python3 tools/check_serial_runtime.py --rom build/serial-test.rom --out local/new-video-run
```

`make test-plain-video` is run by CI. The full serial runtime now checks actual
rasters after initial boot, commands, warm boot and cold reset, in addition to
its existing disk/console tests. Serial communication uses generated PTYs and
the normal RAM-monitor/platform bootstrap and disk host. The public ROM fixture
is source-built; that run does not qualify the historical ROM's floppy-probe
sequence or any physical video electrical behavior.

`tools/check_plain_video.py --before DIR` additionally accepts old `.cim` and
matching `.lst` files to reproduce the stopped-CRT case. Those old artifacts
were rebuilt from the recorded pre-fix source revision without altering it.

## Completed validation

- Python suite: 63 tests passed, one skipped.
- [Classic runtime](../reports/video-classic-runtime.json): all 43 cases passed.
- [Full serial runtime](../reports/video-serial-runtime.json): completed, including
  exact raster comparisons at boot, after console commands, warm boot and cold
  reset; disk corruption recovery, host restart, keyboard input, persistence,
  read-only protection and disk-full handling also passed.
- [Final serial smoke run](../reports/video-serial-basic.json): all five checks
  passed using the final probe, including both raster comparisons. The full run
  used the same production platform but preceded the probe-only change to
  publish capture metadata atomically; each report records its emulator hash.
- [Reproducibility](../reports/reproducible.json): 28 outputs matched byte for
  byte after a fresh build.
- DAC integration suite and video address/undefined-behavior sanitizers passed.
  RAVI tests passed (106 tests, 47 skips), and CRT 1.1 qualification passed all
  twelve fixed patterns, two complete cycles, negative variants and fault cases.

All these results are emulator/software evidence. Physical display validation
remains pending.
