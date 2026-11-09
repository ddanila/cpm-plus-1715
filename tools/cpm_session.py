#!/usr/bin/env python3
"""Persistent Robotron serial CP/M sessions (Linux)."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import pty
import select
import signal
import socket
import subprocess
import sys
import termios
import threading
import time
import tty
import uuid

from evidence import atomic_json
from serial_session import (ROOT, HostService, Console, assert_device_unused,
                            bootstrap, digest, lock_session, positive, validate_artifacts)

SCHEMA = 1
LIMIT = 262144
REPLAY = 65536


def read_json(path):
    return json.loads(path.read_text())


def config_at(session):
    config = read_json(session/'identity.json')
    if config.get('schema') != SCHEMA or config.get('kind') != 'managed-robotron1715':
        raise ValueError('not a managed session; use the original serial_boot.py for legacy sessions')
    return config


def socket_path(session):
    path = str(session/'control.sock')
    if len(os.fsencode(path)) >= 108:
        raise ValueError('session path too long for Unix socket; choose a shorter path')
    return path


def request(session, action):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.settimeout(5)
        client.connect(socket_path(session))
        client.sendall(json.dumps({'action': action}).encode()+b'\n')
        line = bytearray()
        while not line.endswith(b'\n'):
            part = client.recv(1)
            if not part:
                raise RuntimeError('supervisor closed connection')
            line.extend(part)
            if len(line) > 8192:
                raise RuntimeError('invalid supervisor response')
        reply = json.loads(line)
        if not reply.get('ok'):
            raise RuntimeError(reply.get('error', 'request rejected'))
        client.settimeout(None)
        return client, reply
    except BaseException:
        client.close()
        raise


def status(session):
    config_at(session)
    try:
        client, reply = request(session, 'status')
        client.close()
        return reply['status']
    except (OSError, RuntimeError):
        state = read_json(session/'status.json') if (session/'status.json').exists() else {}
        try:
            with lock_session(session/'session.lock'):
                state['live'] = False
                if state.get('state') in ('starting', 'running'):
                    state.update(state='failed', error='supervisor disappeared; inspect evidence before resume')
        except BlockingIOError:
            state.update(live=True, state='starting-or-unresponsive')
        return state


def clean_disk(session):
    if Path(str(session/'disk.img')+'.jhj').exists():
        raise ValueError('pending crash journal; retain evidence, no automatic repair')
    if (session/'disk.img').stat().st_size != 819200:
        raise ValueError('invalid session disk size')


def validate_config(config, session):
    is_pty = str(Path(config['serial']).resolve()).startswith('/dev/pts/')
    if bool(config['emulator']) != is_pty:
        raise ValueError('emulator sessions require a PTY; physical endpoints require hardware mode')
    image, platform = validate_artifacts(Path(config['image']), Path(config['platform']))
    for field in ('image', 'platform', 'host'):
        if digest(Path(config[field])) != config[field+'_sha256']:
            raise ValueError(field+' identity mismatch')
    if platform != (ROOT/'build/platform-serial.cim').read_bytes():
        raise ValueError('requires current serial platform; classic/floppy platform rejected')
    if not os.access(config['host'], os.X_OK):
        raise ValueError('host is not executable')
    clean_disk(session)
    validate_artifacts(session/'disk.img', Path(config['platform']))
    return platform


def initialize(a, session):
    if (session/'identity.json').exists():
        config = config_at(session)
        if a.serial and str(Path(a.serial).absolute()) != config['serial']:
            raise ValueError('serial differs from stored configuration')
        for name in ('image', 'platform', 'host'):
            if getattr(a, name) is not None:
                raise ValueError('artifact overrides apply only to new sessions')
        if a.read_only or a.emulator:
            if a.read_only and not config['read_only'] or a.emulator and not config['emulator']:
                raise ValueError('mode differs from stored configuration')
        return config
    if a.command != 'boot' or not a.serial:
        raise ValueError('new session requires boot --serial DEVICE')
    if any(p.name != 'session.lock' for p in session.iterdir()):
        raise ValueError('new session directory must be empty')
    image = (a.image or ROOT/'out/cpm-plus-1715-serial.img').resolve()
    platform = (a.platform or ROOT/'build/platform-serial.cim').resolve()
    host = (a.host or ROOT.parent/'8080-cosim/build/jukuhost').resolve()
    data, code = validate_artifacts(image, platform)
    if code != (ROOT/'build/platform-serial.cim').read_bytes():
        raise ValueError('requires current serial platform')
    config = dict(schema=SCHEMA, kind='managed-robotron1715', serial=str(Path(a.serial).absolute()),
                  image=str(image), platform=str(platform), host=str(host),
                  image_sha256=digest(image), platform_sha256=digest(platform), host_sha256=digest(host),
                  emulator=a.emulator, read_only=a.read_only, framing='9600 8O2', requires_boot=True)
    is_pty = str(Path(config['serial']).resolve()).startswith('/dev/pts/')
    if a.emulator != is_pty:
        raise ValueError('--emulator requires a PTY and cannot open physical devices')
    (session/'disk.img').write_bytes(data)
    atomic_json(session/'identity.json', config)
    return config


def launch(a, session):
    session.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(session, 0o700)
    socket_path(session)
    with lock_session(session/'session.lock') as lock:
        config = initialize(a, session)
        validate_config(config, session)
        if a.command == 'resume' and config['requires_boot']:
            raise ValueError('session requires a fresh guest boot; resume refused')
        if not config['emulator']:
            assert_device_unused(config['serial'])
        run = session/'runs'/uuid.uuid4().hex
        run.mkdir(parents=True)
        state = dict(state='starting', live=True, run=str(run), mode=a.command,
                     serial=config['serial'], disk=str(session/'disk.img'),
                     read_only=config['read_only'], hardware_executed=not config['emulator'])
        atomic_json(session/'status.json', state)
        with (run/'supervisor.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_serve',
                '--session', str(session), '--lock-fd', str(lock.fileno()), '--mode', a.command,
                '--boot-timeout', str(a.boot_timeout)], pass_fds=(lock.fileno(),),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    if a.command == 'boot':
        print('Waiting for fresh guest boot at 9600 8O2. Power on now; leave floppy drives empty.', flush=True)
    until = time.monotonic()+a.boot_timeout+30
    while time.monotonic() < until:
        state = read_json(session/'status.json')
        if state['state'] == 'running':
            if a.detach:
                print('Session running:', session)
                return 0
            return attach(session)
        if state['state'] == 'failed' or process.poll() is not None:
            raise RuntimeError(state.get('error', 'supervisor exited; inspect '+str(run)))
        time.sleep(.05)
    raise TimeoutError('startup still pending; inspect status and stop explicitly if needed')


def serve(a, session):
    # The inherited lock belongs to this process for its entire lifetime.
    lock = os.fdopen(a.lock_fd, 'a+b')
    config = config_at(session)
    state = read_json(session/'status.json')
    run = Path(state['run'])
    state['pid'] = os.getpid()
    server = None
    clients = {}
    attached = None
    stopping = False
    history = bytearray()
    pending_input = bytearray()
    service = None
    startup_done = threading.Event()
    startup_thread = None

    def startup_control():
        while not startup_done.is_set():
            if not select.select([server], [], [], .05)[0]:
                continue
            try:
                client, _ = server.accept()
                with client:
                    client.settimeout(.2)
                    line = bytearray()
                    while not line.endswith(b"\n") and len(line) < 4096:
                        part = client.recv(1)
                        if not part:
                            break
                        line.extend(part)
                    action = json.loads(line)["action"]
                    reply = {"ok": True, "status": dict(state)}
                    if action not in ("status", "stop"):
                        reply = {"ok": False, "error": "session is still starting"}
                    client.sendall(json.dumps(reply).encode()+b"\n")
                    if action == "stop":
                        os.kill(os.getpid(), signal.SIGTERM)
            except (OSError, ValueError, KeyError, TypeError):
                pass

    def interrupted(*_):
        raise KeyboardInterrupt('supervisor terminated')

    def deadline(*_):
        raise TimeoutError('bootstrap deadline exceeded')

    def publish():
        atomic_json(session/'status.json', state)
        atomic_json(run/'result.json', state)

    def drop(client):
        nonlocal attached
        if attached is client:
            attached = None
        clients.pop(client, None)
        client.close()

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGALRM, deadline)
    try:
        platform = validate_config(config, session)
        publish()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        path = Path(socket_path(session))
        path.unlink(missing_ok=True)
        server.bind(str(path)); os.chmod(path, 0o600)
        server.listen(8); server.setblocking(False)
        startup_thread = threading.Thread(target=startup_control, daemon=True)
        startup_thread.start()
        with ExitStack() as stack:
            sys.path.insert(0, str(ROOT.parent/'ravi/src'))
            from ravi.transport import SerialTransport
            if not config['emulator']:
                assert_device_unused(config['serial'])
            port = stack.enter_context(SerialTransport(config['serial'], 9600,
                parity='N' if config['emulator'] else 'O', stop_bits=2, exclusive=True))
            terminal, slave = pty.openpty()
            stack.callback(os.close, terminal); stack.callback(os.close, slave)
            tty.setraw(terminal); tty.setraw(slave)
            service = HostService(Path(config['host']), config['serial'], port.fd,
                                  session/'disk.img', os.ttyname(slave), run, float('inf'), guard_parent=True)
            stack.callback(service.stop)
            state['host_epochs'] = service.epochs
            if a.mode == 'boot':
                config['requires_boot'] = True
                atomic_json(session/'identity.json', config)
                signal.setitimer(signal.ITIMER_REAL, a.boot_timeout)
                bootstrap(port, platform, run, a.boot_timeout)
                service.start(readonly=config['read_only'])
                console = Console(terminal, run/'console.bin', service.check)
                console.expect(b'A>', a.boot_timeout)
                history.extend(console.output[-REPLAY:])
                signal.setitimer(signal.ITIMER_REAL, 0)
                config['requires_boot'] = False
                atomic_json(session/'identity.json', config)
            else:
                service.start(readonly=config['read_only'])
            serial_health = select.poll()
            serial_health.register(port.fd, 0)
            capture = stack.enter_context((run/'console.bin').open('ab'))
            os.set_blocking(terminal, False)
            startup_done.set()
            startup_thread.join()
            state.update(state='running', live=True, error=None)
            publish()
            while not stopping:
                if any(events & (select.POLLERR | select.POLLHUP | select.POLLNVAL)
                       for _, events in serial_health.poll(0)):
                    raise RuntimeError('serial link disconnected; explicit recovery required')
                service.check()
                readable, writable, _ = select.select([server, terminal]+list(clients),
                    ([terminal] if pending_input else [])+[c for c,v in clients.items() if v['out']], [], .05)
                if terminal in readable:
                    data = os.read(terminal, 4096)
                    if not data:
                        raise RuntimeError('host console disconnected')
                    capture.write(data); capture.flush()
                    history.extend(data); del history[:-REPLAY]
                    if attached is not None:
                        clients[attached]['out'].extend(data)
                if terminal in writable:
                    count = os.write(terminal, pending_input)
                    del pending_input[:count]
                if server in readable:
                    client, _ = server.accept(); client.setblocking(False)
                    if len(clients) >= 16:
                        client.close()
                    else:
                        clients[client] = dict(buf=bytearray(), out=bytearray(), ready=False,
                                               close=False, deadline=time.monotonic()+5)
                for client in list(clients):
                    entry = clients[client]
                    try:
                        if client in readable:
                            data = client.recv(4096)
                            if not data:
                                drop(client); continue
                            if client is attached:
                                if len(pending_input)+len(data) > LIMIT:
                                    drop(client); continue
                                pending_input.extend(data)
                            elif not entry['ready']:
                                entry['buf'].extend(data)
                                if len(entry['buf']) > 4096:
                                    drop(client); continue
                                if b'\n' in entry['buf']:
                                    line, extra = bytes(entry['buf']).split(b'\n', 1)
                                    action = json.loads(line)['action']
                                    reply = {'ok': True}
                                    if action == 'status':
                                        reply['status'] = dict(state, console_attached=attached is not None)
                                    elif action == 'stop':
                                        stopping = True
                                    elif action == 'attach' and attached is None:
                                        attached = client
                                    else:
                                        reply = {'ok': False, 'error': 'console already attached or invalid action'}
                                    entry['out'].extend(json.dumps(reply).encode()+b'\n')
                                    entry['ready'] = True
                                    entry['close'] = client is not attached
                                    if client is attached:
                                        entry['out'].extend(b'\r\n[Previous console output]\r\n'+history+b'\r\n[Live console; Ctrl-] d detaches]\r\n')
                                        pending_input.extend(extra)
                        if entry['out'] and (client in writable or stopping):
                            count = client.send(entry['out'])
                            del entry['out'][:count]
                        if len(entry['out']) > LIMIT or entry['close'] and not entry['out'] or not entry['ready'] and time.monotonic() > entry['deadline']:
                            drop(client)
                    except (OSError, ValueError, KeyError, TypeError):
                        drop(client)
            state.update(state='stopped', live=False)
    except BaseException as exc:
        state.update(state='failed', live=False, error=repr(exc))
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        startup_done.set()
        if startup_thread is not None:
            startup_thread.join(timeout=1)
        for client in list(clients):
            drop(client)
        if server is not None:
            server.close()
            Path(socket_path(session)).unlink(missing_ok=True)
        state['working_sha256'] = digest(session/'disk.img')
        state['journal_pending'] = Path(str(session/'disk.img')+'.jhj').exists()
        publish()
        lock.close()
    return 0 if state['state'] == 'stopped' else 1


class EscapeFilter:
    def __init__(self):
        self.pending = False

    def feed(self, data):
        output = bytearray()
        for value in data:
            if self.pending:
                self.pending = False
                if value == ord('d'):
                    return bytes(output), True
                output.append(29)
                if value != 29:
                    output.append(value)
            elif value == 29:
                self.pending = True
            else:
                output.append(value)
        return bytes(output), False


def attach(session):
    client, _ = request(session, 'attach')
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd) if os.isatty(fd) else None
    escape = EscapeFilter()
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}
    for sig in handlers:
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if saved is not None:
            tty.setraw(fd)
        while True:
            readable, _, _ = select.select([client, fd], [], [])
            if client in readable:
                data = client.recv(65536)
                if not data:
                    return 0
                sys.stdout.buffer.write(data); sys.stdout.buffer.flush()
            if fd in readable:
                data = os.read(fd, 4096)
                if not data:
                    return 0
                data, detach = escape.feed(data)
                if data:
                    client.sendall(data)
                if detach:
                    return 0
    finally:
        if saved is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        client.close()


def snapshot(a, session):
    if not a.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in a.name):
        raise ValueError('snapshot name must contain only letters, digits, hyphens or underscores')
    with lock_session(session/'session.lock'):
        config = config_at(session)
        clean_disk(session)
        directory = session/'snapshots'/a.name
        if a.command == 'snapshot':
            directory.mkdir(parents=True, exist_ok=False)
            image = directory/'disk.img'
            with image.open('xb') as stream:
                stream.write((session/'disk.img').read_bytes()); stream.flush(); os.fsync(stream.fileno())
            atomic_json(directory/'identity.json', dict(schema=SCHEMA, sha256=digest(image),
                platform_sha256=config['platform_sha256'], source_sha256=config['image_sha256']))
        else:
            meta = read_json(directory/'identity.json')
            image = directory/'disk.img'
            if (meta['schema'] != SCHEMA or meta['platform_sha256'] != config['platform_sha256']
                    or meta['source_sha256'] != config['image_sha256'] or meta['sha256'] != digest(image)
                    or image.stat().st_size != 819200):
                raise ValueError('snapshot integrity or compatibility mismatch')
            rollback = session/'snapshots'/('rollback-'+uuid.uuid4().hex)
            rollback.mkdir(parents=True)
            with (rollback/'disk.img').open('xb') as stream:
                stream.write((session/'disk.img').read_bytes()); stream.flush(); os.fsync(stream.fileno())
            atomic_json(rollback/'identity.json', dict(meta, sha256=digest(rollback/'disk.img')))
            # Persist boot requirement before replacing media, including interrupted restores.
            config['requires_boot'] = True
            atomic_json(session/'identity.json', config)
            temp = session/('restore-'+uuid.uuid4().hex+'.tmp')
            with temp.open('xb') as stream:
                stream.write(image.read_bytes()); stream.flush(); os.fsync(stream.fileno())
            os.replace(temp, session/'disk.img')
            print('Restored; fresh guest boot required. Rollback:', rollback.name)
    return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('boot', 'resume', 'attach', 'status', 'stop', 'snapshot', 'restore', '_serve'):
        q = sub.add_parser(name)
        q.add_argument('--session', type=Path, required=True)
        if name in ('boot', 'resume'):
            q.add_argument('--serial')
            for option in ('image', 'platform', 'host'):
                q.add_argument('--'+option, type=Path)
            q.add_argument('--emulator', action='store_true')
            q.add_argument('--read-only', action='store_true')
            q.add_argument('--detach', action='store_true')
            q.add_argument('--boot-timeout', type=float, default=120)
        if name == 'status':
            q.add_argument('--json', action='store_true')
        if name in ('snapshot', 'restore'):
            q.add_argument('--name', required=True)
        if name == '_serve':
            q.add_argument('--lock-fd', type=int, required=True)
            q.add_argument('--mode', choices=('boot', 'resume'), required=True)
            q.add_argument('--boot-timeout', type=float, required=True)
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    session = a.session.resolve()
    os.umask(0o077)
    try:
        if hasattr(a, 'boot_timeout'):
            positive(a.boot_timeout)
        if a.command == '_serve':
            return serve(a, session)
        if a.command in ('boot', 'resume'):
            return launch(a, session)
        if a.command == 'attach':
            return attach(session)
        if a.command == 'status':
            value = status(session)
            print(json.dumps(value, indent=2) if a.json else f"{value.get('state')}: {value.get('disk', session/'disk.img')}\n{value.get('error') or ''}")
            return 0
        if a.command == 'stop':
            client, _ = request(session, 'stop'); client.close()
            until = time.monotonic()+15
            while time.monotonic()<until:
                if not status(session).get('live'):
                    return 0
                time.sleep(.05)
            raise TimeoutError('service has not released ownership')
        return snapshot(a, session)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
