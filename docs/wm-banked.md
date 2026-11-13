# Banked CP/M Plus on the 1715M

The W4 launcher defaults to banked CP/M with a serial console, persistent
host-backed A: and B:, physical floppies C: and D:, and volatile RAM disk E:.
Local video and keyboard console drivers are not part of this profile. W2/W3 and classic 64 KiB 1715 builds remain nonbanked.

Build with `make wm-banked`. The existing W4 boot command in
[wm-serial.md](wm-serial.md) selects the matching banked artifacts at 9600,
41600 or 62400 baud. Upload and readback are at E000h, entry E033h. The
launcher validates the platform, disk, system and rate against a generated
manifest before opening the physical port. The serial wire protocol and W4
ROM are unchanged.

For the previous W4 system, build `make wm-9600 wm-fast wm-62400` and pass
`--nonbanked` to `tools/serial_wm_w4.py` for both boot and attach. An old
nonbanked session requires that option. Profiles cannot be mixed within a
session. Boot always creates a new session disk; it never upgrades an existing
disk in place. Copy user files offline into a separately prepared new image
using the repository's disk tools, retaining the newly built CPM3.SYS and
CCP.COM. Rebuild the matching manifest after an intentional image change.

## Five-drive layout and physical media

| Drive | Storage | Persistence |
| --- | --- | --- |
| A: | Serial system image | Session `disk.img` |
| B: | Additional serial image | Session `disk-b.img` |
| C: | First physical floppy | Diskette |
| D: | Second physical floppy | Diskette |
| E: | 96 KiB RAM disk | Cleared by a fresh OS boot |

The banked launcher creates an empty native 800 KiB B: image by default.
`--drive-b image.img` supplies a source copied into the new session;
`--drive-b-read-only` protects B:, and `--read-only` protects both serial
images. Keep the same options when attaching. Earlier two-drive sessions
have a different identity: migrate files offline into a new session instead
of changing their identity by hand.

C:/D: currently use the native 800 KiB layout: 80 cylinders, two heads,
five 1024-byte sectors (IDs 1–5) per head, exposed as 40 CP/M records per
logical track. Other diskette geometries are not autodetected. Each 128-byte
write reads and merges a whole sector before DMA writes it back. Reads do
not require write permission; ordinary physical writes start locked after
cold boot. Serial read-only options do not govern physical media.

`FORMAT C PROBE` recalibrates and reports readiness without writing disk
contents. `FORMAT C ERASE` irreversibly formats **all** of C:, verifies all
800 sectors as E5, and only then unlocks C: for filesystem writes. Use D in
place of C only when its diskette may be erased. An error locks both physical
drives and stops the motor. `FORMAT C LOCK` locks both drives and stops the
motor. It does not flush application buffers: finish file operations first.
The resulting disk is an empty filesystem, not a bootable system disk.

DMA uses the UA858 at port 00h and FDC data endpoint 41h, with the CPU
interrupts disabled as in the serial BIOS. The stock S550 control sequence
and motherboard schematic were used to correct motor control and transfer
mode. This remains a serial-console port; local display refresh and keyboard
support are separate work. Physical read/write error recovery is bounded;
a bad disk returns a CP/M error rather than redirecting I/O to serial media.

## Memory

This profile requires the reference CAS-PROM mapping: selectors 1–4 provide
four independent 0000h–BFFFh regions and share base RAM at C000h–FFFFh.
That is 208 KiB addressable RAM, not 256 KiB. The boot loader checks low-bank
isolation and stops with a boot error if a required bank aliases another.
This is not a full RAM diagnostic or qualification of a specimen's CAS PROM.

| Region | Use |
| --- | --- |
| Selector 1, below C000h | CP/M bank 0: banked BDOS at 8C00h, BIOS data/buffers at BA00h |
| Selector 2, below C000h | CP/M bank 1: application TPA and CCP |
| Selectors 3 and 4, below C000h | Two 48 KiB halves of E: |
| C000h–C5FFh, common | Resident BDOS and SCB |
| C600h–DFFFh, common | Resident BIOS; DMA floppy driver D000h–DBFFh, sector buffer DC00h–DFFFh |
| E000h–F5FFh, common | Serial platform and filesystem loader |
| F600h–F6FFh, common | Platform/BIOS stack |
| F700h–F7FFh | Reserved scratch, used by the TPA acceptance diagnostic |
| F800h–FFFFh | Reserved; no local display service |

The application ceiling is C000h; CCP's resident loader uses some of that
space. Acceptance requires at least 46 KiB of advertised TPA and writes and
reads every byte below the actual advertised ceiling. The generated memory
map and SYS header are checked during the build.

SELMEM changes execution banks; SETBNK independently selects the disk DMA
bank. XMOVE applies to one MOVE, then ordinary moves resume in the execution
bank. Copies and selector changes execute from common memory with common
stacks. Serial disk I/O stages 128-byte records in common RAM before copying
to or from the selected DMA bank. Directory buffers and allocation data live
in CP/M bank 0. RAM-disk banks are not offered to CP/M's buffer allocator.

## RAM disk and boot validation

E: has 96 KiB raw capacity, 1 KiB blocks, 64 directory entries and 94 KiB file
capacity. It survives warm boots and disk resets. A fresh OS boot formats it;
power loss also loses its contents. Save anything important to A: or B: before
rebooting. There is no automatic persistence, recovery or degraded-bank mode.

The loader scans the full directory and accepts the generated two-extent SYS
in either extent order with fragmented blocks. It validates extent lengths,
block bounds, duplicate allocations and allocations shared with other files.
It checks the header and both segment CRCs before entering the BIOS. This is
a generated-system loader: replacing CPM3.SYS requires rebuilding its matching
platform and manifest. Invalid images and unavailable banks stop visibly.

## Verification

Use the revisions in `tools/wm-dependencies.json`. Build the emulator and host
as described in wm-serial.md, then run:

```sh
make test-banked test-floppy test-formatter wm-probe DAC=/path/to/dac-emulation
python3 tools/check_banked_reproducible.py
python3 tools/check_w4_runtime.py --banked --extended --fragmented \
  --baud 62400 --host /path/to/jukuhost --rom /path/to/rom-w4.bin \
  --out local/banked-62400
```

The 62400 CI campaign also uses `--ram-fill 0xaa` to check startup with
nonzero power-on RAM. This initializes memory before the first ROM instruction;
the ROM still receives and starts the platform over serial normally.

Repeat the extended suite at 9600 and 41600, with `--corrupt-read` at 41600.
Run a separate `--banked --read-only` campaign. Boot rejection cases use
`--fault header`, `payload`, `duplicate`, `foreign`, and `missing-bank`, each
with a fresh output directory. Faults alter private images or the emulator's
CAS fixture; they never change source media or physical hardware.

Tests cover instruction-executed BIOS banking and DMA, copy boundaries,
zero-length/one-shot moves, invalid RAM-disk addresses, the advertised TPA,
full directory/full disk, random records, deletion/reuse, an 80 KiB A:↔E:
round trip, warm boots, cold clearing, SUBMIT and SHOW. Extended suites inject
destructive E: diagnostics only into private test images. Do not run those
diagnostics against a RAM disk containing files you want to keep.

CI runs the emulator campaigns on Linux and macOS, rebuilds the tools and
images in a fresh tree, and packages only evidence matching current source,
probe, ROM, host and image fingerprints. `tools/package_banked.py` requires
all three rates, all rejection cases, read-only/retry coverage, and an explicit
fresh-build reproducibility report. Packages include the nonbanked fallback.

## Physical acceptance

Emulator qualification does **not** establish physical 1715M compatibility.
Before a hardware campaign, verify the actual CAS-PROM mapping and all four
RAM banks with the existing Ravi diagnostics. Use a new disposable session
and known-working W4 ROM and serial adapter.

Boot at 9600 first. Check sign-on, DIR/SHOW, copies A:→E:→A: with independent
host-side byte comparison, repeated Ctrl-C warm boots, and preservation of E:.
Repeat with a file larger than 48 KiB. Start a new OS boot and confirm E: is
empty while A: remains intact. Repeat at 41600 and 62400, retaining upload
readback, serial logs, checksums and session identity. Only successful physical
campaigns should be described as hardware qualification.

The checked-in [runtime reports](../reports/banked/) and
[fresh-build report](../reports/banked-reproducible.json) record the initial
Linux emulator qualification. The accompanying local regression run passed
62 Python tests plus the instruction-executed BIOS probe. No physical hardware
was accessed for these reports.


## PC001 bank-transfer correction — 2026-11-12

The following historical results predate the five-drive layout; their B: was
the RAM disk now assigned to E:.

Physical testing found that the original scalar `LDAX D` / `MOV M,A` copy
loop wrote the source bank when port 24h selected different source and
destination banks. CCP.COM consequently loaded into system bank 1 rather
than application bank 2. The same code passed the current emulator, whose
memory model applies the destination selector to every write.

The BIOS MOVE routine now uses Z80 `LDIR`, exchanging DE/HL around it to
preserve the CP/M calling convention and retaining the zero-length guard.
On PC001, separate 64-byte tests with distinct initial source/destination
patterns showed the scalar loop modifying only bank 1 and LDIR modifying
only bank 2. A checkpoint build returned to W4 automatically; readback then
confirmed all 3,200 CCP bytes in application bank 2 with the corrected routine.
No EPROM change is required.

Robotron's [SCP 3.0 version 0002 customer notice](https://forum.maxiol.com/index.php?act=Attach&id=9079&type=post)
also describes interbank transfers using LDIR or DMA. The emulator now models
measured memory-cycle bank selection, with 20 physical instruction cases as
regression expectations. CP/M CI pins that correction and runs its bank-bus
regression; reverting the BIOS to scalar copies fails the BIOS probe. See the
[model and measurement limits](https://github.com/ddanila/dac-emulation/blob/e53c19710a3d1a498082fa3fc60f4cfaa63ce52c/docs/robotron-bank-bus.md).

The corrected build passed [physical PC001 acceptance at 62400](../reports/hardware-banked-pc001-20261112.json):
47 KiB TPA test, B: full-directory/full-disk/random-record/reuse tests,
three warm boots preserving files, an independently compared 80 KiB round trip,
and a cold OS restart clearing B: while retaining host-backed A:. SHOW reports
94 KiB free on the empty B: drive. Launcher-to-prompt time was 16.8 seconds.
The installed W4 4.0.0 ROM was unchanged. This is one machine at one CP/M rate,
not a long soak or a replacement for the remaining physical acceptance cases.


A subsequent [physical reconnect and soak test](../reports/hardware-reconnect-soak-pc001-20261112.json)
passed at 62400. Two host-service restarts, each with a two-second disconnected
interval, recovered console and A:/B: reads in about six seconds without target
reset or power cycling. Five fresh 80 KiB round trips with warm boots ran for
354 seconds; all 400 KiB of readback matched. The closed host epoch reported
zero retries and UART errors. PIP needs space for both an existing file and its
replacement, so the repeated-copy test erases its test destinations first.
An initial capacity-limited attempt is recorded separately and excluded from
the successful soak rounds. CP/M and the final host were left running at A>.

## Video adapter hardware probe

`make test-video` builds `build/video-test.cim` (VIDTEST.COM) and exercises it
in the emulator. On PC001 with W4 4.1.0 and the qualified banked 62400 platform,
it checks/restores 4 KiB character RAM and 2 KiB screen RAM (mirrored over the
4 KiB CPU window), plus controller stop/start status. It does not enable a local
console. See [qualification and exact compatibility constraints](../reports/rom41-pc001-20261113/video/README.md)
before running it on another configuration.
