# Disk-image tools

These commands operate on the classic 800 KiB raw profile only. They do not
convert 1715W boot code or qualify historical images with different geometry.

```sh
python3 tools/disk_image.py list out/cpm-plus-1715.img
python3 tools/disk_image.py check out/cpm-plus-1715.img
python3 tools/disk_image.py add out/cpm-plus-1715.img NOTES.TXT notes.txt --output out/with-notes.img
python3 tools/disk_image.py extract out/with-notes.img NOTES.TXT --output out/extracted.txt
```

`add` and `extract` require a new output path and refuse existing files, including
aliases of the input. Additions preserve the reserved boot area and unrelated
files; failures detected during validation or allocation do not modify the input.
An OS-level output failure may leave a partial new output file: delete that file
before retrying. `--replace` explicitly permits replacing an existing CP/M file
in the new image, not overwriting the source image. User-0 `CPM3.SYS` and `CCP.COM`
remain protected; rebuild those with `make`.

Names are case-insensitive CP/M 8.3 names without wildcards or paths. Extensions
are optional. `--user 0` through `--user 15` select independent user areas;
`--attributes RSA` sets read-only, system and archive flags (any subset).
Extraction retains logical 128-byte record padding, including Ctrl-Z or E5 bytes.
The directory does not reliably establish the original host byte length. Imports
pad the final record and allocation block with E5; empty files use a directory
entry and no blocks.

The checker validates extent order, record counts, attributes across extents,
block bounds and exclusive block ownership. It supports contiguous preallocated
tail blocks within an extent, but rejects holes and short intermediate extents.
CP/M 3 label, timestamp and password entry types are rejected explicitly in this
version. The generated base image does not use those features. Keep an untouched
copy of historical media; unsupported metadata is not proof that it is corrupt.

Disk layout is unchanged: 20 KiB reserved, 128 directory entries, 2 KiB blocks,
390 allocation blocks including the two directory blocks, EXM=0, 16-bit block
numbers. Multi-extent tests include files large enough to cross the EX/S2 boundary.
