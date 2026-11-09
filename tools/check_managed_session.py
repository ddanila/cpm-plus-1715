#!/usr/bin/env python3
"""Qualify the production managed CLI using timed emulator PTYs only."""
import argparse
import json
import os
from pathlib import Path
import pty
import signal
import subprocess
import sys
import termios
import time
import tty

from evidence import atomic_json, sources
from serial_session import ROOT, Console, digest
from serial_scenarios import basic_console, file_utilities, patterned_file
from media import inspect
from cpm_session import status, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--suite', choices=('lifecycle', 'failures'), default='lifecycle')
    a = parser.parse_args()
    a.out = a.out.resolve(); a.out.mkdir(parents=True, exist_ok=False)
    manifest = sources()
    result = dict(status='running', complete=False, hardware_executed=False, suite=a.suite,
                  source_sha256=manifest, rom_sha256=digest(a.rom),
                  emulator_sha256=digest(ROOT/'build/serial-probe'),
                  host_sha256=digest(ROOT.parent/'8080-cosim/build/jukuhost'), cases=[])
    source = ROOT/'out/cpm-plus-1715-serial.img'
    original = digest(source)
    wire, device = pty.openpty()
    controls, commands = os.pipe()
    tty.setraw(wire); tty.setraw(device)
    serial = os.ttyname(device)
    session = a.out/'session'
    emu = None
    terminal = slave = client = console = None
    saved = None
    logs = []
    clients = []
    sessions = [session]

    def case(name):
        result['cases'].append(dict(name=name, status='passed'))
        atomic_json(a.out/'result.json', result)
        print(name+' PASS', flush=True)

    def cli(command, *args, target=session, expected=0, timeout=160):
        proc = subprocess.run([sys.executable, str(ROOT/'tools/cpm_session.py'), command,
            '--session', str(target), *map(str, args)], capture_output=True, timeout=timeout)
        with (a.out/'cli.log').open('ab') as stream:
            stream.write(('\n'+command+' '+str(args)+'\n').encode()+proc.stdout+proc.stderr)
        assert proc.returncode == expected, (command, proc.returncode, proc.stdout, proc.stderr)
        return proc

    def spawn_emulator():
        nonlocal emu
        log = (a.out/f'emulator-{len(logs)}.log').open('wb'); logs.append(log)
        emu = subprocess.Popen([str(ROOT/'build/serial-probe'), str(a.rom), str(wire),
            str(a.out/'ram.bin'), str(controls)], pass_fds=(wire, controls), stderr=log)

    def connect(initial=False):
        nonlocal terminal, slave, client, console, saved
        terminal, slave = pty.openpty()
        saved = termios.tcgetattr(slave)
        args = [sys.executable, str(ROOT/'tools/cpm_session.py'), 'boot' if initial else 'attach',
                '--session', str(session)]
        if initial:
            args += ['--serial', serial, '--emulator']
        client = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        clients.append(client)
        console = Console(terminal, a.out/f'client-{len(clients)}.bin',
                          lambda: assert_alive(client))
        console.expect(b'[Live console; Ctrl-] d detaches]', 160 if initial else 10)

    def assert_alive(proc):
        if proc.poll() is not None:
            raise RuntimeError('client exited unexpectedly')

    def detach(abrupt=False):
        nonlocal client, terminal, slave
        if abrupt:
            client.send_signal(signal.SIGTERM)
        else:
            os.write(terminal, b'\x1dd')
        client.wait(timeout=10)
        assert termios.tcgetattr(slave) == saved, 'terminal not restored'
        os.close(terminal); os.close(slave)
        terminal = slave = client = None
        until = time.monotonic()+5
        while time.monotonic()<until:
            state = status(session)
            if not state.get('console_attached'):
                break
            time.sleep(.05)
        assert status(session)['state']=='running'

    def wait_state(target, wanted, timeout=30):
        until = time.monotonic()+timeout
        while time.monotonic()<until:
            state = status(target)
            if state['state'] == wanted:
                return state
            time.sleep(.05)
        raise TimeoutError((wanted, state))

    def reset():
        os.write(commands, b'R'); time.sleep(.1)

    try:
        if a.suite == 'failures':
            # No guest exists for these bootstrap timeout/interrupt cases.
            cli('boot', '--serial', serial, '--emulator', '--detach', '--boot-timeout', '.5', expected=1)
            assert status(session)['state']=='failed'
            cli('resume', '--detach', expected=1)
            case('bootstrap timeout and resume refusal')
            process = subprocess.Popen([sys.executable, str(ROOT/'tools/cpm_session.py'), 'boot',
                '--session', str(session), '--detach', '--boot-timeout', '60'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            until=time.monotonic()+10
            while time.monotonic()<until:
                try:
                    s, _ = request(session, 'status'); s.close(); break
                except (OSError, RuntimeError): time.sleep(.05)
            cli('stop')
            assert process.wait(timeout=10)==1
            case('stop during bootstrap releases ownership')
            spawn_emulator()
            cli('boot', '--detach')
            connect()
            console.command('DIR', b'P1715TST')
            detach()
            state=status(session)
            children=Path(f"/proc/{state['pid']}/task/{state['pid']}/children").read_text().split()
            assert len(children)==1, children
            os.kill(int(children[0]), signal.SIGKILL)
            wait_state(session, 'failed')
            case('native host failure recorded without automatic restart')
            cli('resume', '--detach')
            connect(); console.command('TYPE HELLO.TXT', b'Native CP/M'); detach()
            os.kill(status(session)['pid'], signal.SIGTERM)
            wait_state(session, 'failed')
            cli('resume', '--detach')
            case('supervisor termination releases ownership and permits explicit resume')
            state=status(session)
            child_ids=Path(f"/proc/{state['pid']}/task/{state['pid']}/children").read_text().split()
            os.kill(state['pid'], signal.SIGKILL)
            wait_state(session, 'failed')
            until=time.monotonic()+10
            while time.monotonic()<until:
                if all(not Path(f'/proc/{pid}/stat').exists() or Path(f'/proc/{pid}/stat').read_text().split()[2]=='Z' for pid in child_ids):
                    break
                time.sleep(.05)
            else: raise AssertionError('orphaned native host')
            case('abrupt supervisor death terminates native host and stale status is detected')
            # A PTY master keeps TIOCEXCL latched after SIGKILL even when every
            # slave descriptor closes. Retire that virtual cable rather than
            # clearing exclusivity behind the production launcher's back.
            emu.terminate(); emu.wait(timeout=10)
            os.close(wire); os.close(device)
            wire, device = pty.openpty()
            tty.setraw(wire); tty.setraw(device)
            serial = os.ttyname(device)
            session = a.out/'linkloss'; sessions.append(session)
            spawn_emulator()
            cli('boot', '--serial', serial, '--emulator', '--detach', target=session)
            emu.terminate(); emu.wait(timeout=10)
            # Close both ends kept by harness so slave reports link loss.
            os.close(wire); wire=-1
            wait_state(session, 'failed')
            case('emulator disconnect stops owned host')
        else:
            spawn_emulator()
            connect(initial=True)
            case('single-command boot, automatic terminal and background service')
            basic_console(console.command)
            console.warm_boot()
            case('built-in terminal editing and Ctrl-C warm boot')
            cli('boot', '--detach', expected=1)
            cli('snapshot', '--name', 'active', expected=1)
            cli('restore', '--name', 'missing', expected=1)
            cli('attach', expected=1)
            case('duplicate ownership, client and live media mutations refused')
            baseline = {k:v.data for k,v in inspect(source.read_bytes()).items()}
            file_utilities(console.command, session/'disk.img', baseline)
            case('production file utilities')
            os.write(terminal, b'P1715TST W\r')
            console.expect(b'P1715TEST v1', 180, len(console.output))
            detach(abrupt=True)
            run=Path(status(session)['run'])
            until=time.monotonic()+600
            while time.monotonic()<until:
                data=(run/'console.bin').read_bytes()
                if b'P1715TEST WRITE PASS' in data and b'\r\nA>' in data.split(b'P1715TEST WRITE PASS', 1)[1]: break
                assert status(session)['state']=='running'
                time.sleep(.2)
            else: raise TimeoutError('detached write')
            patterned_file(session/'disk.img')
            connect(); console.command('P1715TST R', b'P1715TEST VERIFY PASS', 600)
            detach()
            case('write continues after client termination; replay, reconnect and integrity')
            cli('stop'); cli('snapshot', '--name', 'saved')
            saved_hash=digest(session/'disk.img')
            cli('resume', '--detach')
            connect(); console.command('P1715TST R', b'P1715TEST VERIFY PASS', 600)
            console.command('PIP LATER.TXT=HELLO.TXT'); detach(); cli('stop')
            assert (0,'LATER.TXT') in inspect((session/'disk.img').read_bytes())
            case('host stop/resume without guest reset preserves files')
            cli('restore', '--name', 'saved')
            assert digest(session/'disk.img')==saved_hash
            rollback=next((session/'snapshots').glob('rollback-*/disk.img'))
            assert (0,'LATER.TXT') in inspect(rollback.read_bytes())
            cli('resume', '--detach', expected=1)
            reset(); cli('boot', '--detach')
            connect(); console.command('P1715TST R', b'P1715TEST VERIFY PASS', 600)
            assert (0,'LATER.TXT') not in inspect((session/'disk.img').read_bytes())
            detach(); cli('stop')
            case('offline snapshot, rollback, mandatory fresh boot and restored integrity')
            # Independent read-only session, reached only after explicit emulator reset.
            readonly=a.out/'readonly'; sessions.append(readonly)
            reset(); cli('boot', '--serial', serial, '--emulator', '--read-only', '--detach', target=readonly)
            session_before=session; session=readonly
            connect(); before=digest(session/'disk.img')
            console.command('PIP BLOCKED.TXT=HELLO.TXT', b'ERROR: MAKE FILE NONRECOVERABLE')
            assert digest(session/'disk.img')==before
            detach(); cli('stop', target=readonly)
            session=session_before
            case('read-only persistent session rejects writes unchanged')
            # Offline failures must leave the disk and source unchanged.
            (session/'disk.img.jhj').write_bytes(b'uncertain')
            cli('resume', '--detach', expected=1)
            cli('snapshot', '--name', 'dirty', expected=1)
            assert (session/'disk.img.jhj').read_bytes()==b'uncertain'
            (session/'disk.img.jhj').unlink()
            identity=session/'identity.json'; config=json.loads(identity.read_text())
            changed=dict(config, host_sha256='incorrect'); identity.write_text(json.dumps(changed))
            cli('resume', '--detach', expected=1); identity.write_text(json.dumps(config))
            case('pending journal and incompatible host refused without repair')
        assert digest(source)==original
        assert sources()==manifest, 'sources changed during qualification'
        result.update(status='passed', complete=True, source_unchanged=True)
    except BaseException as exc:
        result.update(status='failed', error=repr(exc))
        print(repr(exc), flush=True)
    finally:
        if client is not None and client.poll() is None:
            client.terminate(); client.wait(timeout=10)
        for target in sessions:
            try:
                if status(target).get('live'):
                    cli('stop', target=target)
            except Exception as exc:
                result.update(status='failed', cleanup_error=repr(exc), complete=False)
        if emu is not None and emu.poll() is None:
            emu.terminate(); emu.wait(timeout=10)
        for stream in logs: stream.close()
        for fd in (wire, device, controls, commands, terminal, slave):
            if fd is not None and fd>=0: os.close(fd)
        result['source_unchanged']=digest(source)==original
        atomic_json(a.out/'result.json', result)
    return 0 if result['status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
