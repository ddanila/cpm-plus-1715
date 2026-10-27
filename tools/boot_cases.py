# SPDX-License-Identifier: MIT
"""Boot-loader fixtures; malformed cases intentionally bypass media validation."""
from media import DIRECTORY, BLOCK, add, inspect


def cases(base):
    first = DIRECTORY
    # Same bytes in five noncontiguous, otherwise free blocks; last dir slot.
    fragmented = bytearray(base)
    entry = bytearray(base[first:first+32])
    for i, block in enumerate((380, 371, 362, 353, 344)):
        old = int.from_bytes(entry[16+2*i:18+2*i], 'little')
        fragmented[DIRECTORY+block*BLOCK:DIRECTORY+(block+1)*BLOCK] = base[DIRECTORY+old*BLOCK:DIRECTORY+(old+1)*BLOCK]
        entry[16+2*i:18+2*i] = block.to_bytes(2,'little')
    fragmented[first] = 0xe5
    fragmented[DIRECTORY+127*32:DIRECTORY+128*32] = entry
    inspect(fragmented)
    yield 'fragmented-last-slot', bytes(fragmented), True
    for name, changes in (
        ('reserved-system-block', {16:1,17:0}),
        ('out-of-range-system-block', {16:134,17:1}),
        ('repeated-system-block', {18:2,19:0}),
        ('short-system-records', {15:71}),
        ('wrong-system-extent', {14:1}),
        ('unused-system-allocation', {26:10}),
    ):
        d = bytearray(base)
        for off, value in changes.items(): d[first+off] = value
        yield name, bytes(d), False
