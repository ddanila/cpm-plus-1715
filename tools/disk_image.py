#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect, check, extract or safely add files to classic 1715 CP/M media."""
import argparse
from pathlib import Path
from media import add, inspect, name_bytes, display_name


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    for command in ('list', 'check', 'extract', 'add'):
        sub = commands.add_parser(command)
        sub.add_argument('image', type=Path)
        if command in ('extract', 'add'):
            sub.add_argument('name')
            sub.add_argument('--user', type=int, choices=range(16), default=0)
            sub.add_argument('--output', type=Path, required=True)
        if command == 'add':
            sub.add_argument('source', type=Path)
            sub.add_argument('--replace', action='store_true')
            sub.add_argument('--attributes', default='', help='subset of RSA')
    a = p.parse_args()
    try:
        image = a.image.read_bytes()
        entries = inspect(image)
        if a.command == 'check':
            print(f'OK: {len(entries)} files; {388-sum(len(f.blocks) for f in entries.values())} free blocks')
        elif a.command == 'list':
            for key in sorted(entries):
                f = entries[key]
                print(f'{f.user:2} {f.name:12} {f.attributes:3} {f.records * 128:7} bytes ({len(f.slots)} extents)')
        else:
            if a.command == 'extract':
                key = (a.user, display_name(name_bytes(a.name)))
                if key not in entries:
                    raise ValueError('file not found')
                data = entries[key].data
            else:
                data = add(image, a.name, a.source.read_bytes(), user=a.user,
                           replace=a.replace, attributes=a.attributes)
            # Exclusive creation refuses input aliases, symlinks and existing files.
            with a.output.open('xb') as output:
                output.write(data)
    except (OSError, ValueError) as exc:
        p.exit(1, f'error: {exc}\n')


if __name__ == '__main__':
    main()
