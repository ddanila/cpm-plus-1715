# Keyboard input during disk operations

The platform has a 128-character ring buffer. A bounded service routine reads at
most three completed SIO bytes per visit, recognizes E0-prefixed 7-bit characters,
and preserves AF, BC, DE and HL. NUL and unprefixed bytes are ignored; a repeated
E0 starts/restarts the pending prefix. Control characters remain ordinary queue
contents for the console caller to interpret.

The service runs during seek delays, every 32 CRC bytes, directory scans, console
calls, and before/after complete disk fields. Active INIR/OTIR field transfers
are unchanged and interrupts remain disabled. This avoids adding interrupt
latency to the disk-byte timing contract. Full queue behavior is explicit: retain
the oldest 128 characters, drop each newest excess character, count the drop,
and continue decoding prefixes correctly. Cold initialization clears queue state
and diagnostics. Stale bytes in unused queue storage are never exposed.

Warm boot retains queued input. While loading CCP, BIOS CONST reports no ready
characters, preventing BDOS/CCP housekeeping from consuming typeahead. The first
blocking CONIN releases it. Receiving and buffering continue during that hold;
queue overflow policy remains the same. The BIOS's unreachable B: descriptors and
buffers were removed to keep the existing BC00h BIOS/9D00h BDOS resident map while
adding this control. The system remains A: only.

`build/keyboard-map.json` exports resident addresses for queue indices, count,
prefix, hold flag, service routine and 16-bit modulo service/decoded/drop counters.
The runner independently counts service visits and measures gaps with 64-bit
counters. The map is included in simulator packages. The platform and its queue
must end below F600h, preserving the existing stack clearance.

## Qualification input envelope

The declared simulated cadence is E0 followed by the character 1,000 CPU clocks
later, then 100,000 clocks until the next E0: 101,000 clocks per character, about
24.3 characters/second at 2.458 MHz. This is the existing fixture cadence delivered
without backpressure. It is **not a measured physical keyboard baud rate**.

The runner's timestamp file attempts every completed byte exactly once, even
when RX is disabled or full. Reports retain the entire schedule, accepted/full/
disabled/late/pending counts, disk counters, exported queue diagnostics and media
comparisons. Events use a monotonic runner clock across resets. Existing paced
command injection remains available for historical qualification.

The guest keyboard workload uses actual BIOS reads, writes and alternating-track
seeks, without BDOS console polling while the test input arrives. It writes an
identical copy of scratch disk records and saves received characters in a separate
host-allocated result file. Host checks require exact input ordering and unchanged
unrelated files. This distinguishes receiver loss from application consumption.

Cases cover three input phases, 256-character ring wrap, 160-character overflow
with a 16-character recovery sequence, orphan/repeated/split prefixes and NUL,
queued commands across warm boot, and reset without scheduled-event replay.
The overflow case must report exactly 32 queue drops, with no receiver loss.
Gap observation is restricted to the scheduled payload window (plus one character
period), excluding boot/idle intervals; it measures gaps between observed service
entries, not electrical FIFO deadlines or an exhaustive phase proof.

Two faster periods, 50,000 and 20,000 clocks, characterize overload. Receiver
rejections are expected to remain visible, and a partial input sequence must not
be reported as a successful complete capture. The model's three-byte FIFO is not
expanded, bytes are not retried, and incoming schedules are never slowed to pass.

This protects the qualified BIOS disk workloads. It does not promise input
retention in arbitrary long-running transients that never call BIOS, nor exact
silicon overrun replacement, serial framing, real keyboard clocking, or physical
floppy gap/timing compatibility. Those still require model extensions or hardware.
