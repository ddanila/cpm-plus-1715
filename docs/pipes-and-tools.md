# PIPEMGR and cpmbox on the serial drive

`make tools` builds CAT, CAL, CP, DU, FIND, HEXDUMP, LS, MV and UNTAR from
pinned cpmbox sources. `make serial` includes these commands in the default
serial image, together with PIPEMGR.RSX, GENCOM.COM, SETDEF.COM and TOOLS.TXT.
The classic image is unchanged. `out/cpm-plus-1715-serial-base.img` preserves
the serial image without the additional tools.

Use `/H` for each command's help. For example:

```
LS *.COM | CAT
CAL 11 2026 | CAT
CAT HELLO.TXT > COPY.TXT
CAT HELLO.TXT >> COPY.TXT
CAT /B DATA.BIN | HEXDUMP
CAT /B SAMPLE.TAR | UNTAR - A:
```

PIPEMGR runs stages sequentially, storing intermediate bytes in disk files.
It is not concurrent execution or a Unix shell. Reserve `PIPEIN.$$$` and
`PIPEOUT.$$$` on A:, user 0, and allow disk space for the largest intermediate
output. `>&` redirects stdout and stderr together; `|&` sends both to the
next stage. A failed cpmbox stage cancels subsequent stages; this is not a
Bash-style aggregate `pipefail` status. A failed named redirection can leave
an empty or partial destination file; the reserved pipe files are removed.

CAT defaults to CP/M text semantics. `/B` preserves bytes, including zero,
Ctrl-Z and bytes above 127. CP, HEXDUMP and UNTAR use binary file access.
CAT and HEXDUMP read stdin without a filename. UNTAR accepts `-` for stdin;
only regular flat 8.3 members are accepted. Invalid checksums, truncated
records, unsupported member types, pathnames, long names and existing
destinations are errors. Extraction is per-file, not an atomic archive
transaction: successfully extracted earlier files remain after a later error.

Pipeline stages must name available `.COM` programs on A: in the current
user area. PIPEMGR checks the next executable before chaining; an unavailable
command cancels the pipe and restores a usable console.

The serial profile supports A: only. FIND never probes other drives. CAL
requires an explicit month/year. Paging is disabled when any PIPEMGR stream
is redirected or piped; console interrupts use BIOS console input rather
than consuming pipeline data.

Binary byte counts use the DOS Plus convention: directory S1 contains the
number of **used** bytes in the last 128-byte record, with zero meaning a
full record. The writer repeats this file-level count in every extent so
readers opening the initial extent receive it. Old files without this metadata retain record-rounded lengths.
Host `media.File.data` still exposes padded records; `exact_data` and
`exact_size` are additional views. No heuristic strips trailing Ctrl-Z from
binary files.

## Existing managed sessions

Stop the managed service first, then run:

```
python3 tools/cpm_session.py install-tools --session /path/to/session
```

Installation holds the session lock and refuses read-only sessions, pending
crash journals, changed tool names, or insufficient capacity. It preserves
other files and user areas. Files already identified by the session's tool
manifest may be replaced; an unrelated `CAT.COM`, for example, is a conflict.
Repeated installation of the same bundle is safe.

The command prints a rollback snapshot name. Restore it with:

```
python3 tools/cpm_session.py restore --session /path/to/session --name tools-rollback-...
```

Both upgrade and restore require a **fresh guest boot**; `resume` is refused.
The rollback contains the disk and configuration, including installed tool
identity. A transaction marker blocks boot after an interrupted installation;
restore its named rollback before continuing.

New sessions retain verified image/platform inputs under `inputs/`, named
by SHA-256. Rebuilding `out/` therefore does not invalidate an existing
session. Older managed sessions are migrated only when their recorded input
hash can be verified, either at the old path or against the retained base
serial build. If neither is available, restore the original input file;
the launcher never substitutes an unverified current image.

## Reproducible build and local changes

Source identities are in `dependencies.json`, provenance beside each vendored
project, and `third_party/tools-inputs.json`. The compiler runs locally under
ZXCC; compiler executables are not installed on guest media. Build diagnostics
are retained in `build/tools/build.log`.

The cpmbox upstream tree is unchanged. `src/cpmbox/hitech.patch` and the shared
`port.c` layer adapt it to the pinned HI-TECH libc: argument cleanup, error
handling, binary modes, paging, safe DU buffers, checked writes and tar
validation. CAL also receives its missing year argument for leap-day counts.

PIPEMGR 1.03 needed a source fix: its direct-output rewrite left the previous
stage's output flag set. `build_pipemgr.py` first reproduces the upstream
binary's complete code and relocation bitmap, then builds the corrected
version with our existing zmac assembler. It also adds a resident failure
exit for file-open/create/write/close errors so a pipeline cannot silently
continue after disk failure. The DOS Plus length convention is retained.
A preflight check also prevents the CCP from remaining attached to pipe input
when the next executable is missing. No Robotron BIOS changes are needed for this integration.

Licenses remain with the upstream sources: cpmbox GPLv3, PIPEMGR GNU Library
GPLv2 (full text in `LICENSES/PIPEMGR-LGPL-2.txt`), and HI-TECH's free-use grant with copyright acknowledgment. The local
cpmbox adaptations use GPLv3-or-later. Qualification-only probes are not
installed in the release image.

## Emulator qualification

`tools/check_tools_runtime.py` boots through the production managed launcher
and native serial host using PTYs. It never opens a physical serial port.

```
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --probe --out local/pipe-probe
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --suite utilities --out local/tools
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --suite streams --out local/tools-streams
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --suite binary --sizes 0,1,127,128,129,16385 --out local/tools-binary
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --suite binary --sizes 49153 --out local/tools-large
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --failure full --out local/tools-full
python3 tools/check_tools_runtime.py --rom build/serial-test.rom --failure readonly --out local/tools-ro
```

The utility, stream and binary suites can run in independent emulator sessions. The largest
pipe can take about 20 minutes through the production 9,600-baud drive protocol;
individual commands have a 30-minute timeout. `--suite all` runs both together.
`--suite core` combines utilities and streams. Use `--upgrade` to exercise a base-image boot, offline installation, fresh boot,
and rollback boot.

The suite records source/image/ROM identities, console and wire evidence,
checks restored TPA, and compares binary results independently using exact
byte metadata after the service stops. Repeat with the historical ROM when
available. These are emulator results, not claims of physical qualification.

### Recorded results

All 51 local tests pass, and `reports/reproducible.json` records a fresh build
matching all 28 tracked outputs. Emulator evidence is retained in:

- `reports/tools-utilities-{public,reference}.json`: all nine commands, all-byte
  binary data, tar extraction, copied/renamed bytes, warm boot and restored TPA.
- `reports/tools-binary-{public,reference}.json` and
  `reports/tools-large-{public,reference}.json`: exact lengths at 0, 1, 127,
  128, 129, 16,385 and 49,153 bytes, plus temporary-file cleanup.
- `reports/tools-streams-{public,reference}.json`: 27 checks per ROM covering
  redirection, append, binary stdin, paging suppression, archive errors,
  missing-command recovery, legacy PIP input and Ctrl-C cleanup.
- `reports/tools-{pipemgr,full-disk,readonly,upgrade}.json`: RSX lifecycle,
  disk-error recovery, and upgrade/fresh-boot/rollback checks.

Each report retains its own source and image identities. Utility and large
binary campaigns preceded the final emergency-exit cleanup adjustment; their
source snapshots differ from the release only in `build_pipemgr.py` and
`pipemgr-error.inc`. The stream, disk-error, RSX and upgrade reports use the
final release source. Earlier native, firmware, managed-session and serial
regression reports remain under `reports/tools-*.json` with their original
identities. No physical machine, serial port or floppy was used.
