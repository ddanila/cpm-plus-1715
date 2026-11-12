# Provenance and licensing

New 1715 code is Copyright (c) 2026 Danila Sukharev, MIT licensed.
The CP/M BIOS glue, regeneration script and tool build recipes derive from
`ddanila/cpm-plus-juku` commit 61b2d5397589e794c0381aa836b7a0da2217e6c8.
Their BSD-2-Clause terms are retained in `third_party/JUKU-LICENSE`.

Digital Research CP/M, its tools and derivatives retain the distribution grant
in `third_party/cpm3/LICENSE.md`; the root MIT license does not replace it.
Pinned source and binary archives are the same 2026-06-07 releases used by Juku.
The vendored ld80 linker is public domain and is not needed by this build.
Zmac retains its source notices (public-domain components and GPL components).
ZXCC 0.5.7 retains the GPL notices in its unmodified source archive. These are
host build tools, not part of the generated guest BIOS. Historical Robotron ROM/OS binaries are not included. The serial targets
reuse the BSD-2-Clause N3 disk and N4 console engines from juku-common;
see `third_party/juku-common/LICENSE-BSD-2-Clause`. They do not include
Juku fonts or its complete ROM.

The reference ROM is an external test input with SHA-256
51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01.
The bootstrap descriptor and hardware drivers are original implementations of
the interfaces documented by the local ROM investigation and Pico1715 project.

The indexed-record guest workload and independent file parser in
`tools/pattern_workload.py` and its `classic_workload.py` helper are reused
under MIT from Pico1715 commit 048954ec200a4024e6b3ae182f62f380a863f5cf.


## cpmbox, PIPEMGR and HI-TECH C

The default serial image includes cpmbox (Kevin Boone, GPLv3), built from the
pinned source under `third_party/cpmbox/upstream`. The local C compatibility layer and cpmbox patch in
`src/cpmbox` are GPLv3-or-later. The original license is included with the source.
PIPEMGR (John Elliott, Jon Saxton and Tony Nicholson) uses GNU Library GPLv2;
its source and original binary are under `third_party/hitech/pipemgr`.
The full GNU Library GPLv2 text is in `LICENSES/PIPEMGR-LGPL-2.txt`.
The build verifies source reproduction before applying the documented fixes.
PIPEMGR modifications, including `src/cpmbox/pipemgr-error.inc`, remain under
the GNU Library GPLv2.
HI-TECH C and its runtime are Copyright HI-TECH Software, used under the
free-use grant reproduced in `third_party/hitech/LICENSE`. Compiler binaries
are build dependencies and are not installed in the CP/M image.

## W/M serial package

The W3/W4 monitors and Ravi launcher support are MIT licensed, Copyright (c)
2026 Danila Sukharev. The native jukuhost retains its BSD-2-Clause terms
(the same copyright and grant reproduced in JUKU-LICENSE). The W/M image
does not include the optional cpmbox or PIPEMGR tools.

The banked 1715M profile uses RESBDOS3.SPR and BNKBDOS3.SPR from the same
pinned Digital Research binary archive. Their source is included in the
matching source archive. The banked BIOS retains the BSD-2-Clause terms of
the existing BIOS glue; its new loader, RAM-disk diagnostics and qualification
tools carry their source-file notices.
