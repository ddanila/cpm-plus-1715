# Boot and BIOS contract

The original generated disk descriptor selects the 80×2×5×1024 MFM format,
loads the reserved-area first stage at 4000h and enters it. The stage copies
our platform services to C000h, then calls their filesystem loader. There are
no calls back into historical ROM routines after handoff.

The loader scans all 128 user-0 directory slots for CPM3.SYS extent zero.
The generated 9216-byte SYS fits one extent and uses 16-bit allocation pointers.
It verifies the nonbanked header, loads the reverse-ordered 128-byte records
into 9D00h–BFFFh and verifies a build-generated CRC-16/CCITT over resident bytes
before jumping to BC00h. Missing files, invalid headers, bad block addresses,
CRC failures and exhausted I/O retries stop with a visible boot error. SYS and
bootstrap form one build; replacing SYS requires rebuilding the image.

The C000h platform has CP/M-compatible service vectors. The CP/M 3 BIOS adapts
these to its native jump table and XDPH. GENCPM enables double allocation
vectors: A: reserves **98 bytes**, two arrays of ceil(390/8). Reserving only 49
bytes corrupts allocation state once the full directory is scanned; the disk-
full fixture is a regression for this failure.

The generated system places the resident loader at 9A00h, BDOS at 9D00h,
SCB below BC00h and BIOS at BC00h. The transient span is 0100h–99FFh, 39168
bytes. Platform code/data must finish below F600h, stack top is F700h, and
F800h–FF7Fh holds 80×24 screen bytes. The assembly listing and build checks
verify the platform bound. CP/M page-zero jumps are installed by the BIOS.

Each logical track is one physical side: cylinder=track/2, head=track%2.
Logical record numbers 1–40 map to five physical sectors with eight records
each. The driver validates CHRN and CRC, performs bounded field searches,
and uses /WAIT-paced block I/O. CRC calculation occurs after stopping capture.
The read cache is tagged by logical track and physical sector, invalidated
on home/reset, cache miss and failed acquisition. Writes preserve the other
seven records, precompute CRC, reacquire the matching ID and transmit a whole
field. Write gating always closes before returning.

Warm boot resets BDOS's multi-record count before loading CCP.COM. The console
receiver is initialized by the bootstrap once; reinitializing it in the CP/M
cold entry could discard already received input. Test command spacing is
explicit because CP/M utilities can consume type-ahead while checking for
abort; the harness does not inject BIOS return values.
