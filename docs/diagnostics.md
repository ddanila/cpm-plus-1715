# Portable guest diagnostics

`P1715TST.COM` is original MIT code using CP/M 2-compatible BDOS calls only.
It is included in the source-built disk and simulator package. It never writes
controller ports or replaces OS interrupt handlers.

- `P1715TST I` (or no argument): display BDOS version and commands; no disk writes.
- `P1715TST W`: explicitly create `P1715TST.DAT` on the current drive/user. Write
  256 independently patterned 128-byte records (32 KiB), crossing an extent.
  An existing filename is refused, never replaced. Close errors are failures.
- Cold boot, then `P1715TST R`: independently open and check exact file length,
  signature and every record in reverse random-read order. No file writes.
- `P1715TST C`: first perform the same complete verification, then delete only
  that verified scratch file. A partial/corrupt file is retained for inspection.
- `P1715TST K`: echo one key for operator assessment. `OBSERVED` is not an
  automated keyboard or serial-electrical qualification.

Use disposable writable media for W/C. Without qualified reserve power, finish
with controller safe eject before turning power off. A guest WRITE PASS means
BDOS completed and closed a file; it does not prove physical SD durability.
Write-protected media may be rejected by the OS with its own error message.
On disk full, a partial file can remain; C deliberately refuses to delete it.
Inspect it and use the OS erase command deliberately if removal is desired.

For stock SCP, insert the built COM into a **new copy** using the checked host
image tool. Never modify the preserved source image:

```
python3 tools/disk_image.py add private-scp.img P1715TST.COM build/p1715test.cim --output scp-diagnostics.img
```

Qualify actual guest execution and independent host reads:

```
python3 tools/check_diagnostics.py --binary build/classic-probe --rom build/test.rom --backend native --out local/new-diagnostics --extended
python3 tools/check_diagnostics.py --binary build/firmware/classic-probe --rom build/test.rom --backend firmware --out local/new-firmware-diagnostics
```

Use `--image` and the reference ROM for local SCP qualification. Reports bind the
program, runner, ROM and media hashes; no private input payload is published.
Runs cover version, write, cold read, collision, corrupted data, verified deletion
and cold absence. Extended CP/M 3 runs add disk-full and write-protection cases.
Every run checks original files are unchanged.

Interrupt stress runs separately: Pico1715's original motherboard-chain and CPU
cost fixture programs execute outside CP/M. Use their existing synthetic runners;
never run those fixtures as a COM program under an OS. The guided bring-up runner
records them as isolated-fixture evidence, not OS diagnostics.
