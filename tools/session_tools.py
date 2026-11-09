"""Offline managed-session input retention and transactional tool installation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid
from evidence import atomic_json
from serial_session import ROOT, digest, lock_session, validate_artifacts
from tool_bundle import bundle, install


def retain_inputs(config, session):
    """Copy verified source identities into the session, including legacy sessions."""
    config = copy.deepcopy(config)
    directory = session/'inputs'; directory.mkdir(exist_ok=True)
    for field, suffix in (('image','.img'), ('platform','.bin')):
        expected = config[field+'_sha256']
        target = directory/(expected+suffix)
        if target.exists():
            if digest(target) != expected: raise ValueError('retained input identity mismatch')
        else:
            candidates = [Path(config[field])]
            if field == 'image': candidates += [ROOT/'out/cpm-plus-1715-serial-base.img']
            source = next((p for p in candidates if p.is_file() and digest(p) == expected), None)
            if source is None: raise ValueError('verified legacy '+field+' unavailable; restore the original input first')
            with target.open('xb') as stream:
                stream.write(source.read_bytes()); stream.flush(); os.fsync(stream.fileno())
        config[field] = str(target.resolve())
    return config


def snapshot_meta(config, image):
    return dict(schema=config['schema'], sha256=digest(image),
                platform_sha256=config['platform_sha256'], source_sha256=config['image_sha256'],
                config=config)


def save_rollback(session, config, prefix='tools-rollback-'):
    directory = session/'snapshots'/(prefix+uuid.uuid4().hex)
    directory.mkdir(parents=True)
    with (directory/'disk.img').open('xb') as stream:
        stream.write((session/'disk.img').read_bytes()); stream.flush(); os.fsync(stream.fileno())
    atomic_json(directory/'identity.json', snapshot_meta(config, directory/'disk.img'))
    return directory


def replace_disk(session, data):
    temporary = session/('install-'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, session/'disk.img')
        fd = os.open(session, os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def install_tools(session):
    from cpm_session import config_at, clean_disk
    with lock_session(session/'session.lock'):
        config = config_at(session)
        clean_disk(session)
        if config.get('read_only'): raise ValueError('read-only session')
        if (session/'tools-transaction.json').exists():
            raise ValueError('interrupted tools transaction; restore its rollback snapshot first')
        old = retain_inputs(config, session)
        validate_artifacts(session/'disk.img', Path(old['platform']))
        data, manifest = install((session/'disk.img').read_bytes(), old.get('tools',{}).get('files'))
        # All conflicts, capacity and hash checks have completed before rollback/mutation.
        rollback = save_rollback(session, old)
        new = copy.deepcopy(old)
        new.update(tools=manifest, requires_boot=True)
        atomic_json(session/'tools-transaction.json', dict(rollback=rollback.name))
        try:
            # Crash between these writes is fail-closed: the transaction marker blocks boot.
            atomic_json(session/'identity.json', new)
            replace_disk(session, data)
            (session/'tools-transaction.json').unlink()
        except BaseException:
            replace_disk(session, (rollback/'disk.img').read_bytes())
            atomic_json(session/'identity.json', old)
            (session/'tools-transaction.json').unlink(missing_ok=True)
            raise
        print('Installed tools; fresh guest boot required. Rollback:', rollback.name)
    return 0
