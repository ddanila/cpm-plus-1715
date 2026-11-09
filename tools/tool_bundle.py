"""Verified default serial utility bundle and non-destructive image installation."""
import hashlib
import json
from pathlib import Path
from media import add, inspect

ROOT = Path(__file__).resolve().parents[1]


def bundle():
    directory = ROOT/'out/tools'
    manifest = json.loads((directory/'manifest.json').read_text())
    data = {}
    expected = {n+'.COM' for n in ('CAT','CAL','CP','DU','FIND','HEXDUMP','LS','MV','UNTAR','GENCOM','SETDEF')} | {'PIPEMGR.RSX','TOOLS.TXT'}
    if manifest.get('schema') != 1 or set(manifest['files']) != expected:
        raise ValueError('invalid tools manifest')
    for name, meta in manifest['files'].items():
        content = (directory/name).read_bytes()
        if len(content) != meta['size'] or hashlib.sha256(content).hexdigest() != meta['sha256']:
            raise ValueError('tool identity mismatch: '+name)
        data[name] = content
    return manifest, data


def install(image, known=None):
    """Pure preflight/install. Existing unrelated names are never overwritten."""
    manifest, payloads = bundle()
    existing = inspect(image)
    known = known or {}
    for name, data in payloads.items():
        old = existing.get((0, name))
        if old:
            digest = hashlib.sha256(old.exact_data).hexdigest()
            if old.exact_data != data and digest != known.get(name, {}).get('sha256'):
                raise ValueError('unrecognized existing tool name: '+name)
            if 'R' in old.attributes:
                raise ValueError('read-only tool: '+name)
        image = add(image, name, data, replace=bool(old), exact=True)
    return image, manifest
