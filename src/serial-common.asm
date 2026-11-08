remote_state: ds 29
net_state: ds 18
net_cache: ds 131
remote_state_end:
; Shared 8080 source executes natively on the Z80. No translated copy.
SHARED_SERIAL equ 1
ROM_ABI_C9 equ 1
ROMNETDISK equ 1
N3MAXRECORDS equ 1
ROMHOSTSTATEBASE equ remote_state
ROMNETSTATEBASE equ net_state
        .8080
        include "third_party/juku-common/platform/rom-abi.inc"
        include "third_party/juku-common/platform/rom-host-services.asm"
        include "third_party/juku-common/platform/netdisk-v3.asm"
        .z80
