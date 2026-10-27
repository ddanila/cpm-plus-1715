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
host build tools, not part of the generated guest BIOS. No Juku ROM services,
fonts, NetDisk code or historical Robotron ROM/OS binaries are included.

The reference ROM is an external test input with SHA-256
51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01.
The bootstrap descriptor and hardware drivers are original implementations of
the interfaces documented by the local ROM investigation and Pico1715 project.

The indexed-record guest workload and independent file parser in
`tools/pattern_workload.py` and its `classic_workload.py` helper are reused
under MIT from Pico1715 commit 048954ec200a4024e6b3ae182f62f380a863f5cf.
