# Qualification boundaries

The runtime suite defines 43 scenarios and records generated-image, build-output,
source, dependency, ROM and runner fingerprints. It executes the guest on the
unchanged Z80/bus seam and checks exported media; it does not intercept BDOS calls.
The report's `rom_profile` distinguishes `public-fixture` from `stock-reference`.
`hardware_executed` remains false.

## Coverage

- Boot and utilities: directory listing, SUBMIT-driven PIP/TYPE/RENAME/SHOW,
  cold persistence, erase/cold deletion, keyboard editing and warm boot.
- Boot loader: guest SET of SYS/RO attributes followed by cold boot, fragmented
  SYS in the final directory slot, reserved/out-of-range/repeated allocations,
  wrong record count, wrong extent and unused allocation pointers.
- Guest storage: four-record BDOS reads and writes, reverse random reads,
  USER isolation/cold directory visibility, full directory with free data blocks,
  a 32 KiB PIP copy, and restoration of multi-record count on warm boot.
- Indexed storage: 256 distinct records across extents, cold comparison,
  deliberate payload corruption, disk full after 160 records and cold comparison.
- Faults: write protection, missing SYS, damaged SYS header/payload, absent media,
  CRC injection, reset during an incomplete write, and a cold read of the recovered
  copy. Host checks require exact recovered contents and unchanged unrelated files.

Host tests separately exercise empty files, padding, attributes, user areas,
EX/S2 boundary crossing, malformed extents/allocations, directory and disk
exhaustion without modifying input, and exclusive output creation. An independent
byte-level oracle checks the original directory/data layout. New platform bytes
in the reserved boot area intentionally change.

Good transfers require zero overrun, underflow, drop, transmit-fault, SIO-error
and rejected-write counters. Negative media tests require absence of the OS prompt
and appropriate transfer activity (none for absent media, nonzero for CRC faults).
The public fixture must emit its boot-error diagnostic. A configured fault alone
is not a pass. Firmware diagnostics, including storage/RTL details, are retained
in each case's stderr and in its report.

The original firmware CRC test did not establish rejection: service initialization
cleared the injected option and the OS booted. The updated host bridge applies
explicit faults after initialization, and the updated suite rejects that prior
false-positive outcome. Earlier 19-case reports should not be read as evidence
of firmware CRC-fault rejection.

## Running and publishing

Build runners with `make probe` or `make firmware-probe`. Their hash-bound sidecar
manifests identify the backend and exact clean dependency commits. The runtime
harness checks these before starting. Unknown ROMs are rejected: use the locally
built public fixture or the reference hash documented in NOTICE.

Each invocation owns a unique run directory under `--out`, with private input
copies and per-case stdout/stderr, RAM, screen and exported image. Timeouts and
SIGINT/SIGTERM terminate and reap the runner process group. A passing report is
written in that run directory and atomically published to `--report` only after
all checks and stable-source/output checks pass. Incomplete runs retain diagnostics
without a success report. Old report files are not evidence for changed sources.

CI runs the full native public-fixture suite, a fresh-tree build comparison of
nine generated artifacts, and a separate firmware/RTL boot, CRC-fault and asynchronous-input smoke.
Packaging accepts explicit reports only and checks fingerprints and the complete
expected case set. The default CI package requires full native public-fixture and
reproducibility reports. `--release` additionally requires full native and firmware
reference-ROM reports. The ZIP includes those selected reports, design/qualification
and disk-tool documentation, licences and a manifest. Fixed ZIP timestamps and
ordering produce identical packages for identical inputs.

## What simulation does not establish

The fixture installs platform services using ordinary Z80 instructions, then
enters the filesystem loader. It does not exercise the stock descriptor or the
4000h bootstrap; the external reference-ROM suites cover those stages. The ROM is
private test input, and its identity is not tied to a physical specimen.

The runner's legacy `rom_handoff_*` counters observe address 0204h. They are not
an OS-success signal for the public fixture, where unrelated code may reach that
address. Exit status must agree with that runner contract; guest screen and media
checks independently determine success. Cycle bounds and optional screen markers
followed by a 20-million-clock tail limit runtime without changing guest state.

Firmware/RTL executes the shared production service/storage C and actual frontend
RTL with a host GPIO/SD HAL. It does not execute RP2350 instructions or measure
SD latency, bus setup/hold, electrical levels or power-loss durability. The model
rejects malformed writes atomically and does not model damaged physical tracks.

The historical command injector waits for SIO FIFO space. The ten additional
keyboard cases use one-shot timestamped arrivals, with phase/wrap/overflow/prefix,
warm-boot/reset checks and faster-rate characterization. See [keyboard](keyboard.md)
for the measured evidence and declared simulation envelope. Neither injector
qualifies physical serial waveforms. Long application command sequences still
use guest SUBMIT so the next command follows completion.

Before physical deployment, verify mainboard revision, connector orientation,
voltage translation and power gates, then measure CTC/SIO clocking, CRT output,
sector timing, seek delays, protection, reset and cold persistence on disposable
media. These remain physical qualification gates.

## Previous disk-tool milestone — 2026-10-27

All 33 cases passed separately with the native/reference-ROM runner, native/public
fixture, and shared firmware/RTL/reference-ROM runner (99 case executions).
All 14 host tests passed, and a fresh source tree reproduced all seven generated
artifacts. Explicit release packaging accepted the current four reports and
produced identical ZIP bytes on repeat invocation.

Implementation CI passed for both repositories:
[CP/M checks](https://github.com/ddanila/cpm-plus-1715/actions/runs/40491963766)
and [Pico1715 checks](https://github.com/ddanila/Pico1715/actions/runs/40491196444).
The final report-only commit does not change the qualified sources or dependency
pins. These results supersede the older firmware report's CRC-fault claim.

## Keyboard reliability milestone — 2026-10-27

All 43 cases passed separately with the native/reference-ROM runner, native/public
fixture, and shared firmware/RTL/reference-ROM runner (129 case executions).
All 17 host tests passed, and a fresh source tree reproduced all nine generated
artifacts. The ten additional cases exercise asynchronous arrivals during BIOS
disk operations, queue wrap/overflow, prefix decoding, warm boot, reset, and
faster-input overload. Scheduled bytes are attempted once without backpressure.

The largest observed service-entry gap across the eight positive keyboard cases
was 86,904 CPU clocks in native/reference-ROM simulation and 87,188 clocks in
firmware/RTL simulation (about 35.5 ms), against the tested 101,000-clock character
period. These are observations within the test windows, not an exhaustive phase
proof or a measured physical keyboard rate. Nominal cases had no FIFO-full
rejections; deliberate queue overflow retained the oldest 128 characters and
counted 32 drops. Faster-input cases exposed receiver loss as expected.

Implementation CI passed for both repositories:
[CP/M checks](https://github.com/ddanila/cpm-plus-1715/actions/runs/40502678499)
and [Pico1715 checks](https://github.com/ddanila/Pico1715/actions/runs/40501975438).
Release packaging accepted all four current reports and produced identical ZIP
bytes on repeat invocation. The final report/documentation commit does not change the qualified sources or
dependency pins. Physical timing and electrical qualification remain outstanding.

## Browser-session milestone — 2026-10-27

The shared classic-session revision passed all 43 cases in five configurations:
three native runs (public/model, reference/model, reference/firmware) and two
WebAssembly runs (public/model and public/firmware): **215 case executions**.
The WASM CLI probes compile the same qualified source and preserve the existing
one-shot keyboard schedules. Reports explicitly distinguish `execution: wasm`
from native execution. Their launchers verify both JavaScript and WASM hashes.

The 17 host tests passed and all nine generated artifacts reproduced from a fresh
source tree. Release packaging accepted all six current reports. Pico1715 also
compared interactive native/WASM session RAM, registers, disk bytes and diagnostics
after boot/commands, export/resume, delayed storage and reset; its backend CI passed
[here](https://github.com/ddanila/Pico1715/actions/runs/40516051826).

Build Node probes with Pico1715's `tools/build_browser.py --probes`, then bind them
with `python3 tools/build_wasm_probe.py` (add `--firmware` for the firmware backend).
Pass the resulting launcher to `tools/check_runtime.py` exactly like a native
probe. Browser UI workflow coverage belongs to DAC's classic-workstation guide;
these reports qualify deterministic simulator execution, not physical hardware.

## Portable diagnostics increment

The bundled `P1715TST.COM` has separate [diagnostic qualification](../reports/diagnostics.json):
nine native CP/M 3 scenarios, seven shared-firmware/RTL CP/M 3 scenarios, and seven
local reference-ROM/SCP scenarios. Reports retain the exact guest program, runner,
ROM and input/output disk hashes. The utility is verified independently against
host-read file contents; cold verification, collision and corruption failures
preserve unrelated files. This adds no physical execution claim.
