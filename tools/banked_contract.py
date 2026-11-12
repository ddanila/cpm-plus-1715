"""SPDX-License-Identifier: MIT. Validate matched banked images before upload."""
import hashlib
import json
from pathlib import Path
from media import inspect
from serial_session import validate_artifacts


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_banked(image, platform, manifest, baud):
    data, code = validate_artifacts(image, platform)
    contract = json.loads(Path(manifest).read_text())
    if (contract['profile'], contract['baud'], contract['platform_start'],
        contract['platform_entry'], contract['platform_limit']) != (
            '1715m-banked', baud, 0xe000, 0xe033, 0xf600):
        raise ValueError('banked profile/rate mismatch')
    if len(code) > 0x1600 or digest(code) != contract['platform_sha256']:
        raise ValueError('banked platform mismatch')
    if digest(data) != contract['image_sha256']:
        raise ValueError('banked image mismatch; rebuild or explicitly upgrade offline')
    system = inspect(data)[(0,'CPM3.SYS')].data
    if digest(system) != contract['sys_sha256']:
        raise ValueError('banked system mismatch')
    if data[136:138] != bytes.fromhex('00e0') or data[144:146] != bytes.fromhex('33e0'):
        raise ValueError('banked bootstrap address mismatch')
    return contract, code


def source_fingerprint(root):
    """Fingerprint build/runtime inputs, including the actual shared serial sources."""
    root = Path(root)
    paths = sorted((root/'src').glob('*.asm'))
    paths += sorted((root/'third_party/juku-common/platform').glob('*.asm'))
    paths += [root/'third_party/juku-common/platform/rom-abi.inc']
    paths += [root/name for name in (
        'Makefile', 'tools/build_banked.py', 'tools/build_image.py',
        'tools/regenerate_cpm3.py', 'tools/media.py', 'tools/banked_contract.py',
        'tools/check_w4_runtime.py', 'tools/wm_probe.c', 'tools/banked_probe.c',
        'tools/wm-dependencies.json', 'tools/serial_wm_w4.py')]
    return digest(b''.join(str(p.relative_to(root)).encode()+b'\0'+p.read_bytes()+b'\0'
                           for p in paths))
