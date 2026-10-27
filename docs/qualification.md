# Qualification boundaries

Reports record generated-image and runner hashes, source fingerprints, screen
captures, controller counters and independent media comparisons. They describe
execution in a model, not a physical 1715 or measured RP2350 timing.

`native-runtime.json` uses the unchanged external reference ROM and timed PIO
controller. `public-runtime.json` uses the source-built entry fixture and the
same Z80/controller model. Each covers 19 scenarios: boot and directory,
SUBMIT-driven utilities, cold persistence, erase and cold deletion, keyboard
editing/warm boot, explicit multi-record warm boot, 256 distinct records across
extents, cold comparison, deliberate corruption, disk full and cold comparison,
write protection, missing SYS, damaged SYS header and payload, absent media,
CRC fault injection and reset during an incomplete write.

The full fixture leaves ten free 2 KiB blocks. The guest must stop after 160
128-byte records; the host independently checks those bytes and the next cold
boot reads them back. This caught and fixed insufficient space for CP/M's
second allocation vector. The ordinary indexed workload checks 32768 bytes.

The native suite's good transfers require zero overrun, underflow, drop,
transmit fault, SIO error and rejected-write counters. Deliberate CRC faults
are negative tests, not successful transfers. Runtime cycle bounds include
room for error handling; an optional literal screen marker followed by 20
million additional CPU clocks cuts otherwise idle test time. Tests still
validate outputs and media independently.

The public fixture does not exercise the original ROM descriptor/4000h stage.
The actual ROM is private test input; no result silently substitutes the fixture
for that ROM. Source-only CI covers the public fixture and uploads a generated
simulator package. The original ROM's identity has not been tied to a physical
specimen, as documented in Pico1715.

Pico1715's runner changes preserve existing defaults. Its nine stock-SCP timed
cases, portable tests and firmware smoke pass; its integration commit also has
a passing GitHub Actions run. The co-simulation builder now forces a final link
after externally compiled C objects change, preventing stale-runner evidence.

Before physical deployment, verify mainboard revision, connector orientation,
voltage translation and board power gates independently. Then qualify CTC/SIO
clocking, keyboard input, CRT output, sector timing, seek delays, protection,
reset and cold persistence on disposable media. The simulator's controller
rejects malformed writes atomically and does not model damaged physical tracks.

The runner's legacy `rom_handoff_*` counters observe the reference ROM's 0204h
exit. They are meaningful only in the external-reference-ROM suite; unrelated
code can execute at that address in the public fixture. Public qualification
uses screen, guest workload and independently parsed disk evidence instead.
Keyboard injection is a paced completed-byte source that waits for modeled SIO
FIFO space. It does not qualify a physical keyboard's baud timing or typing
through long, interrupt-disabled disk operations.

## Shared firmware/RTL result

`firmware-runtime.json` passes the same 19 cases using the unchanged reference
ROM, production `firmware/service.c` and `firmware/store.c`, the actual frontend
RTL, and the host GPIO/SD HAL. It verifies the indexed 32768-byte file, 160-record
disk-full boundary and cold persistence. Reset during an incomplete write
preserves the model-owned image at reset and recovers to the CP/M boot path.

This does not execute RP2350 instructions or qualify measured SD latency,
physical bus setup/hold times, electrical levels or power-loss durability.
The backend is pinned to Pico1715 aeb29a62f7c81a28da992b42f30fddbe25193028;
the native motherboard is pinned to DAC 98f8f808c08ce21f6b98a00b95185f1e2226e70d.
