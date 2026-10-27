# SPDX-License-Identifier: MIT
"""Checked CP/M 3 media for the nonbanked classic 1715 profile.

Lengths are logical records, not exact original byte counts. CP/M 3 label and
password entries are retained but deliberately rejected by this v1 writer.
"""
from dataclasses import dataclass
import re

SIZE = 819200
DIRECTORY = 20480
DIRECTORY_END = 24576
BLOCK = 2048
BLOCKS = 390
PROTECTED = {'CPM3.SYS', 'CCP.COM'}


def name_bytes(name):
    name = name.upper()
    if not re.fullmatch(r"[A-Z0-9!#$%&'()+\-@^_`{}~]{1,8}(\.[A-Z0-9!#$%&'()+\-@^_`{}~]{1,3})?", name):
        raise ValueError('expected a CP/M 8.3 name without wildcards or paths')
    stem, _, ext = name.partition('.')
    return (stem.ljust(8) + ext.ljust(3)).encode('ascii')


def display_name(raw):
    stem = raw[:8].decode('ascii').rstrip()
    ext = raw[8:].decode('ascii').rstrip()
    return stem + ('.' + ext if ext else '')


@dataclass(frozen=True)
class File:
    user: int
    name: str
    attributes: str
    slots: tuple
    blocks: tuple
    records: int
    data: bytes


def inspect(image):
    if len(image) != SIZE:
        raise ValueError('expected an 819200-byte raw 1715 image')
    groups, owners = {}, {}
    for off in range(DIRECTORY, DIRECTORY_END, 32):
        e = image[off:off + 32]
        if e[0] == 0xe5:
            continue
        if e[0] > 15:
            raise ValueError(f'unsupported directory entry type {e[0]:02x} at {off}')
        raw = bytes(x & 127 for x in e[1:12])
        try:
            name = display_name(raw)
            if name_bytes(name) != raw:
                raise ValueError('noncanonical name')
        except (UnicodeError, ValueError) as exc:
            raise ValueError(f'invalid name at {off}') from exc
        if e[12] & 0xe0 or e[14] & 0xc0 or e[15] > 128:
            raise ValueError(f'invalid extent metadata for {name}')
        extent = e[12] + 32 * e[14]
        blocks = tuple(int.from_bytes(e[i:i + 2], 'little') for i in range(16, 32, 2))
        needed = (e[15] + 15) // 16
        # A preallocated tail is legal, but missing blocks within live records
        # and allocated blocks after a zero slot are not supported here.
        tail_zero = False
        for i, b in enumerate(blocks):
            if not b:
                if i < needed:
                    raise ValueError(f'missing block for {name}')
                tail_zero = True
                continue
            if tail_zero or not 2 <= b < BLOCKS or b in owners:
                raise ValueError(f'invalid/shared block {b} for {name}')
            owners[b] = (e[0], name)
        attrs = ''.join(c for i, c in [(9, 'R'), (10, 'S'), (11, 'A')] if e[i] & 128)
        data = b''.join(image[DIRECTORY + b * BLOCK:DIRECTORY + (b + 1) * BLOCK]
                        for b in blocks[:needed])[:e[15] * 128]
        groups.setdefault((e[0], name), []).append((extent, off, blocks, e[15], attrs, data))
    result = {}
    for key, rows in groups.items():
        rows.sort()
        if [r[0] for r in rows] != list(range(len(rows))):
            raise ValueError(f'missing/duplicate extent for {key}')
        if any(r[3] != 128 for r in rows[:-1]):
            raise ValueError(f'short intermediate extent for {key}')
        if len({r[4] for r in rows}) != 1:
            raise ValueError(f'inconsistent attributes for {key}')
        result[key] = File(*key, rows[0][4], tuple(r[1] for r in rows),
                          tuple(b for r in rows for b in r[2] if b),
                          sum(r[3] for r in rows), b''.join(r[5] for r in rows))
    return result


def add(image, name, data, *, user=0, replace=False, attributes='', system=False, start_block=None):
    """Return a new validated image; never mutate caller-owned input."""
    if not 0 <= user <= 15:
        raise ValueError('user must be 0..15')
    raw = name_bytes(name)
    name = display_name(raw)
    attributes = attributes.upper()
    if any(c not in 'RSA' for c in attributes) or len(set(attributes)) != len(attributes):
        raise ValueError('attributes must be a subset of RSA')
    if not system and user == 0 and name in PROTECTED:
        raise ValueError('rebuild system files with make; general import is protected')
    entries = inspect(image)
    existing = entries.get((user, name))
    if existing and not replace:
        raise ValueError('file exists; replacement must be explicit')
    disk = bytearray(image)
    if existing:
        for slot in existing.slots:
            disk[slot] = 0xe5
        del entries[(user, name)]
    used = {b for f in entries.values() for b in f.blocks}
    free = [b for b in range(2, BLOCKS) if b not in used and (start_block is None or b >= start_block)]
    slots = [i for i in range(DIRECTORY, DIRECTORY_END, 32) if disk[i] == 0xe5]
    records = (len(data) + 127) // 128
    count = max(1, (records + 127) // 128)
    if len(slots) < count:
        raise ValueError('directory full')
    if len(free) < (records + 15) // 16:
        raise ValueError('disk full')
    padded = data + bytes([0xe5]) * (records * 128 - len(data))
    next_block = 0
    for extent in range(count):
        chunk = padded[extent * 16384:(extent + 1) * 16384]
        e = bytearray(32)
        e[0] = user
        e[1:12] = raw
        for i, c in [(9, 'R'), (10, 'S'), (11, 'A')]:
            if c in attributes:
                e[i] |= 128
        e[12], e[14], e[15] = extent & 31, extent >> 5, len(chunk) // 128
        for j in range((len(chunk) + BLOCK - 1) // BLOCK):
            b = free[next_block]
            next_block += 1
            e[16 + 2*j:18 + 2*j] = b.to_bytes(2, 'little')
            part = chunk[j * BLOCK:(j + 1) * BLOCK]
            off = DIRECTORY + b * BLOCK
            disk[off:off + BLOCK] = part + bytes([0xe5]) * (BLOCK - len(part))
        disk[slots[extent]:slots[extent] + 32] = e
    inspect(disk)
    return bytes(disk)
