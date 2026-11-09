#!/usr/bin/env python3
"""One power-on, one unattended campaign; all CP/M disk I/O uses serial A:."""
import argparse
import os
import pty
import re
import signal
import subprocess
import sys
import time
import tty
from contextlib import ExitStack
from pathlib import Path

from evidence import atomic_json
from media import inspect
from pattern_workload import fixture, nearly_full, record
from serial_session import lock_session, assert_device_unused, ROOT, Console, HostService, bootstrap, digest, positive, validate_artifacts
from serial_scenarios import basic_console, file_utilities, patterned_file, baseline_unchanged

UNSUPPORTED = {
    'physical cold reset and power-loss recovery': 'no external power/reset controller',
    'local keyboard and CRT/video': 'serial-only observation; no input injection',
    'physical floppy and controller': 'excluded; A: is host-backed serial media only',
    'alternate system-image boot rejection': 'requires another fresh loader session',
}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--board', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--image', type=Path, default=ROOT/'out/cpm-plus-1715-serial.img')
    p.add_argument('--platform', type=Path, default=ROOT/'build/platform-serial.cim')
    p.add_argument('--host', type=Path, default=ROOT.parent/'8080-cosim/build/jukuhost')
    p.add_argument('--boot-timeout', type=float, default=120)
    p.add_argument('--timeout', type=float, default=3600)
    p.add_argument('--emulator', action='store_true', help='PTY validation only; never a physical device')
    return p


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    try:
        positive(a.boot_timeout); positive(a.timeout)
        original, platform = validate_artifacts(a.image, a.platform)
        if platform != (ROOT/'build/platform-serial.cim').read_bytes():
            raise ValueError('hardware campaign requires the current serial platform; run make serial')
        if not a.host.is_file() or not os.access(a.host, os.X_OK):
            raise ValueError('build the native host first')
        help_result = subprocess.run([str(a.host.resolve()), '--help'], capture_output=True, timeout=5)
        if help_result.returncode or b'--test-corrupt-read-reply-once' not in help_result.stdout + help_result.stderr:
            raise ValueError('native host lacks Robotron test support; rebuild the pinned host')
        is_pty = str(Path(a.serial).resolve()).startswith('/dev/pts/')
        if a.emulator != is_pty:
            raise ValueError('PTYs require --emulator; --emulator cannot open a physical device')
        # All fixture edits precede the first physical byte and target boot.
        prepared = nearly_full(fixture(original, records=4096, seed=83, expect_full=True), 48)
        baseline = {k: v.data for k, v in inspect(prepared).items()}
        a.out.mkdir(parents=True, exist_ok=False)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        p.error(str(exc))
    working = a.out/'disk.img'
    working.write_bytes(prepared)
    started = time.monotonic()
    deadline = started+a.timeout
    result = dict(status='running', complete=False, supported_suite_passed=False,
                  hardware_executed=False, board=a.board, serial=a.serial,
                  framing='9600 8O2', mode='emulator' if a.emulator else 'hardware',
                  source_sha256=digest(a.image), prepared_sha256=digest(working),
                  platform_sha256=digest(a.platform), host_sha256=digest(a.host),
                  cases=[], unsupported=UNSUPPORTED, host_epochs=[], phase='preflight')
    service = None
    current = None
    exit_code = 1

    def checkpoint():
        result['elapsed_seconds'] = round(time.monotonic()-started, 3)
        atomic_json(a.out/'result.json', result)

    def run(name, action):
        nonlocal current
        current = dict(name=name, status='running')
        result['cases'].append(current)
        result['phase'] = name
        checkpoint()
        action()
        current['status'] = 'passed'
        checkpoint()
        print(name+' PASS', flush=True)

    def timed_out(*_):
        raise TimeoutError('campaign or bootstrap deadline exceeded')

    def interrupted(*_):
        raise KeyboardInterrupt('campaign interrupted')

    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM)}
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGALRM, timed_out)
    signal.setitimer(signal.ITIMER_REAL, a.timeout)
    checkpoint()
    try:
        with ExitStack() as stack:
            stack.enter_context(lock_session(a.out/'session.lock'))
            if not a.emulator:
                assert_device_unused(a.serial)
            sys.path.insert(0, str(ROOT.parent/'ravi/src'))
            from ravi.transport import SerialTransport
            port = stack.enter_context(SerialTransport(a.serial, 9600,
                parity='N' if a.emulator else 'O', stop_bits=2, exclusive=True))
            terminal, console_fd = pty.openpty()
            stack.callback(os.close, terminal)
            stack.callback(os.close, console_fd)
            tty.setraw(terminal); tty.setraw(console_fd)
            service = HostService(a.host, a.serial, port.fd, working, os.ttyname(console_fd), a.out, deadline)
            # Stop children before releasing the physical descriptor.
            stack.callback(service.stop)
            result['host_epochs'] = service.epochs
            console = Console(terminal, a.out/'console.bin', service.check, deadline)
            result['hardware_executed'] = not a.emulator
            result['phase'] = 'waiting for initial power-on'
            checkpoint()
            print('Listening at 9600 8O2. Power on now; leave physical drives empty.', flush=True)
            boot_deadline = min(deadline, time.monotonic()+a.boot_timeout)
            signal.setitimer(signal.ITIMER_REAL, max(.001, boot_deadline-time.monotonic()))
            def boot():
                bootstrap(port, platform, a.out, a.boot_timeout)
                result['monitor_sha256'] = digest(a.out/'monitor-readback.bin')
                service.start()
                console.expect(b'A>', max(.001, boot_deadline-time.monotonic()), 0)
            run('verified serial boot', boot)
            signal.setitimer(signal.ITIMER_REAL, max(.001, deadline-time.monotonic()))
            command = console.command
            run('console, editing, DIR and TYPE', lambda: basic_console(command))
            run('copy, rename and SUBMIT', lambda: file_utilities(command, working, baseline))
            def write_pattern():
                command('P1715TST W', b'P1715TEST WRITE PASS', 600)
                patterned_file(working)
            run('pattern write and independent integrity', write_pattern)
            run('existing-file collision', lambda: command('P1715TST W', b'P1715TEST COLLISION FAIL'))
            def restart_host():
                service.stop()
                time.sleep(2)
                service.start()
                command('TYPE HELLO.TXT', b'Native CP/M Plus on Robotron 1715')
                command('P1715TST R', b'P1715TEST VERIFY PASS', 600)
                patterned_file(working)
            run('host restart without guest reset', restart_host)
            def warm():
                console.warm_boot()
                command('P1715TST R', b'P1715TEST VERIFY PASS', 600)
                patterned_file(working)
            run('warm boot and persistence', warm)
            def corrupt():
                service.stop()
                service.start(corrupt=True)
                epoch = service.epochs[-1]['index']
                command('PIP RETRY.TXT=HELLO.TXT')
                assert inspect(working.read_bytes())[(0, 'RETRY.TXT')].data == baseline[(0, 'HELLO.TXT')]
                service.stop()
                log = (a.out/f'host-{epoch}.log').read_text()
                injections = re.findall(r'test-fault=read-crc injected=1 seq=(\d+)', log)
                assert len(injections) == 1, 'expected exactly one CRC fault'
                assert re.search(r'seq='+injections[0]+r'\b[^\n]*duplicate', log), 'read was not retried'
                service.start()
                command('ERASE RETRY.TXT')
            run('one corrupt read reply and verified retry', corrupt)
            def cleanup():
                command('P1715TST C', b'P1715TEST CLEAN PASS', 600)
                command('ERASE NEW.TXT')
                baseline_unchanged(working, baseline)
            run('cleanup and baseline integrity', cleanup)
            def full():
                command('PICOTEST', b'PICO DISK FULL OK', 900)
                data = inspect(working.read_bytes())[(0, 'PICOTEST.TXT')].data
                assert data and len(data) % 128 == 0
                assert data == b''.join(record(i, 83) for i in range(len(data)//128))
                run_files = inspect(working.read_bytes())
                for key, value in baseline.items():
                    assert run_files[key].data == value
                command('ERASE PICOTEST.TXT')
                console.warm_boot()
                write_pattern()
                command('P1715TST R', b'P1715TEST VERIFY PASS', 600)
                command('P1715TST C', b'P1715TEST CLEAN PASS', 600)
                baseline_unchanged(working, baseline)
            run('disk-full, recovery and preserved baseline', full)
            def readonly():
                service.stop()
                service.start(readonly=True)
                before = digest(working)
                command('PIP BLOCKED.TXT=HELLO.TXT', b'ERROR: MAKE FILE NONRECOVERABLE')
                assert digest(working) == before, 'read-only image changed'
                baseline_unchanged(working, baseline)
            run('read-only host rejection and unchanged image', readonly)
            assert digest(a.image) == result['source_sha256'], 'source image changed'
            result.update(status='passed', complete=True, supported_suite_passed=True,
                          phase='finished', manual_power_cycle_required=False)
            exit_code = 0
    except BaseException as exc:
        if isinstance(exc, (SystemExit, GeneratorExit)):
            raise
        if current is not None and current['status'] == 'running':
            current.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=repr(exc))
        result.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                      complete=False, supported_suite_passed=False,
                      error=repr(exc), manual_power_cycle_required=current is not None)
        exit_code = 130 if isinstance(exc, KeyboardInterrupt) else 1
        print('FAIL: '+repr(exc), flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        try:
            result['working_sha256'] = digest(working)
            result['source_unchanged'] = digest(a.image) == result['source_sha256']
            if not result['source_unchanged']:
                raise RuntimeError('source image changed')
        except (OSError, RuntimeError) as exc:
            result.update(status='failed', complete=False, supported_suite_passed=False,
                          evidence_error=repr(exc))
            exit_code = 1
        checkpoint()
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
