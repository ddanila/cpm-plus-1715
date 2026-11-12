"""Shared bootstrap, native host ownership and console transactions for serial tests."""
import hashlib
import fcntl
import stat
import math
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from importlib.resources import files

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def positive(value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError('timeout must be finite and positive')
    return value


def validate_artifacts(image, platform):
    data = Path(image).read_bytes()
    code = Path(platform).read_bytes()
    if len(data) != 819200 or not 0 < len(code) < 0x3600:
        raise ValueError('invalid Robotron artifacts')
    source = int.from_bytes(data[133:135], 'little') - 0x4000
    if not 0 < source < 128 or data[128+source:128+source+len(code)] != code:
        raise ValueError('platform/image mismatch')
    return data, code


def bootstrap(port, platform, session, timeout, boot=None):
    from ravi.transport import LoggedTransport
    from ravi.backends.robotron1715.boot import StockBoot
    from ravi.backends.robotron1715.monitor import Monitor, IDENTITY
    positive(timeout)
    with (session/'bootstrap-tx.bin').open('wb') as tx, (session/'bootstrap-rx.bin').open('wb') as rx:
        wire = LoggedTransport(port, rx, tx)
        if boot is None:
            boot = StockBoot(wire)
            boot.handshake(timeout)
        payload = files('ravi.backends.robotron1715').joinpath('monitor.bin').read_bytes()
        boot.upload(0x4000, payload)
        boot.execute(0x4000)
        monitor = Monitor(wire)
        if monitor.response() != [IDENTITY]:
            raise RuntimeError('wrong monitor')
        actual = b''.join(monitor.read_memory(0x4000+i, min(256, len(payload)-i))
                          for i in range(0, len(payload), 256))
        (session/'monitor-readback.bin').write_bytes(actual)
        if actual != payload:
            raise RuntimeError('monitor verification failed')
        for i in range(0, len(platform), 256):
            monitor.write_memory(0xc000+i, platform[i:i+256])
        actual = b''.join(monitor.read_memory(0xc000+i, min(256, len(platform)-i))
                          for i in range(0, len(platform), 256))
        (session/'platform-readback.bin').write_bytes(actual)
        if actual != platform:
            raise RuntimeError('platform verification failed')
        monitor.start(0xc033)


def host_command(host, serial, image, console, log, capture, readonly=False, fd=None,
                 corrupt=False):
    command = [str(Path(host).resolve()), '--machine', 'robotron1715', '--resume-disk',
               '--serial', serial, '--volume', str(image), '--console-pty', console,
               '--log', str(log), '--capture', str(capture)]
    if not readonly:
        command.append('--writable')
    if fd is not None:
        command += ['--serial-fd', str(fd)]
    if corrupt:
        command.append('--test-corrupt-read-reply-once')
    return command


class HostService:
    """One child at a time; the supervisor retains the original serial descriptor."""
    def __init__(self, host, serial, fd, image, console, out, deadline, guard_parent=False):
        self.host, self.serial, self.fd = host, serial, fd
        self.image, self.console, self.out = image, console, out
        self.deadline = deadline
        self.guard_parent = guard_parent
        self.process = None
        self.epochs = []
        self.stream = None

    def check(self):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('native host exited unexpectedly')
        if time.monotonic() >= self.deadline:
            raise TimeoutError('campaign deadline exceeded')

    def start(self, readonly=False, corrupt=False):
        if self.process is not None:
            raise RuntimeError('host already running')
        if Path(str(self.image)+'.jhj').exists():
            raise RuntimeError('unclean journal before host transition; retain evidence')
        index = len(self.epochs)
        log = self.out/f'host-{index}.log'
        capture = self.out/f'wire-{index}.bin'
        self.epochs.append(dict(index=index, read_only=readonly, corrupt_read_once=corrupt,
                                image_sha256=digest(self.image), host_sha256=digest(self.host)))
        self.stream = (self.out/f'host-{index}-process.log').open('wb')
        args = host_command(self.host, self.serial, self.image, self.console, log, capture,
                            readonly, self.fd, corrupt)
        if self.guard_parent:
            args = [sys.executable, str(ROOT/'tools/serial_host_guard.py'), str(os.getpid())]+args
        self.process = subprocess.Popen(args, pass_fds=(self.fd,), stdout=self.stream,
                                        stderr=subprocess.STDOUT, start_new_session=True)
        until = min(self.deadline, time.monotonic()+15)
        while time.monotonic() < until:
            self.check()
            if log.exists() and b'phase=netdisk' in log.read_bytes():
                return
            time.sleep(.05)
        raise TimeoutError('native host did not become ready')

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=5)
            self.epochs[-1]['exit_code'] = self.process.returncode
            self.process = None
        if self.stream is not None:
            self.stream.close()
            self.stream = None


class Console:
    def __init__(self, fd, path, check=lambda: None, deadline=float('inf')):
        self.fd, self.path, self.check, self.deadline = fd, Path(path), check, deadline
        self.output = bytearray()
        self.path.write_bytes(b'')

    def expect(self, token, timeout=180, start=None):
        positive(timeout)
        start = len(self.output) if start is None else start
        until = min(self.deadline, time.monotonic()+timeout)
        while time.monotonic() < until:
            self.check()
            if token in self.output[start:]:
                return bytes(self.output[start:])
            if b'CP/M 3 boot error:' in self.output[start:]:
                raise RuntimeError('guest boot error')
            if select.select([self.fd], [], [], min(.05, max(0, until-time.monotonic())))[0]:
                data = os.read(self.fd, 4096)
                if not data:
                    raise RuntimeError('console disconnected')
                self.output.extend(data)
                with self.path.open('ab') as stream:
                    stream.write(data)
        raise TimeoutError(f'timeout waiting for {token!r}; tail={bytes(self.output[-400:])!r}')

    def command(self, text, marker=None, timeout=180):
        at = len(self.output)
        os.write(self.fd, text.encode('ascii')+b'\r')
        prompt = at
        marker = marker or (text.encode('ascii') if text else None)
        if marker:
            self.expect(marker, timeout, at)
            prompt = self.output.index(marker, at)+len(marker)
        self.expect(b'A>', timeout, prompt)
        return bytes(self.output[at:])

    def warm_boot(self):
        at = len(self.output)
        os.write(self.fd, b'\x03')
        self.expect(b'A>', start=at)


def lock_session(path):
    stream = path.open('a+b')
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    return stream


def assert_device_unused(path):
    """Reject visible existing owners before changing termios; TIOCEXCL guards new opens."""
    device = os.stat(path)
    if not stat.S_ISCHR(device.st_mode):
        raise ValueError('serial endpoint must be a character device')
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            descriptors = list((process/'fd').iterdir())
        except (PermissionError, FileNotFoundError):
            continue
        for descriptor in descriptors:
            try:
                opened = descriptor.stat()
            except (PermissionError, FileNotFoundError):
                continue
            if stat.S_ISCHR(opened.st_mode) and opened.st_rdev == device.st_rdev:
                raise RuntimeError(f'serial device already open by PID {process.name}')
