#!/usr/bin/env python3
"""Run the guest, Ravi bootstrap and production host through timed SIO/PTYs."""
import argparse
import hashlib
import json
import os
import pty
import select
import signal
import subprocess
import sys
import time
import tty
from pathlib import Path
from media import inspect
from serial_session import Console
from serial_scenarios import basic_console, file_utilities, patterned_file

ROOT = Path(__file__).resolve().parents[1]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--suite', choices=['basic', 'full', 'media'], default='full')
    a = p.parse_args()
    rom_hash = sha(a.rom)
    if rom_hash == '51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01':
        profile = 'reference-ROM-cold-boot-four-unreadable-scratch-drives'
    elif rom_hash == sha(ROOT/'build/serial-test.rom'):
        profile = 'public-serial-fixture'
    else:
        p.error('unrecognized ROM')
    a.out.mkdir(parents=True, exist_ok=False)
    wire, device = pty.openpty()
    terminal, console = pty.openpty()
    control, commands = os.pipe()
    for fd in [wire, device, terminal, console]: tty.setraw(fd)
    env = dict(os.environ, PYTHONPATH=str(ROOT.parent/'ravi/src'))
    emulator_log = (a.out/'emulator.log').open('wb')
    emu = subprocess.Popen([str(ROOT/'build/serial-probe'), str(a.rom), str(wire),
                            str(a.out/'ram.bin'), str(control)],
                           pass_fds=(wire, control), stderr=emulator_log)
    launcher = None
    logs = []
    output = bytearray()
    original = ROOT/'out/cpm-plus-1715-serial.img'
    initial_hash = sha(original)
    initial_files = {k:v.data for k,v in inspect(original.read_bytes()).items()}
    result = dict(complete=False, hardware_executed=False, suite=a.suite,
                  rom_profile=profile, rom_sha256=rom_hash,
                  image_sha256=initial_hash, platform_sha256=sha(ROOT/'build/platform-serial.cim'),
                  emulator_sha256=sha(ROOT/'build/serial-probe'),
                  host_sha256=sha(ROOT.parent/'8080-cosim/build/jukuhost'), cases=[])
    def case(name):
        result['cases'].append(name)
        (a.out/'progress.json').write_text(json.dumps(result, indent=2)+'\n')
        print(name, 'PASS', flush=True)
    def start(mode, session, image=original, readonly=False):
        nonlocal launcher
        log = (a.out/f'launcher-{len(logs)}.log').open('wb'); logs.append(log)
        args = [sys.executable, str(ROOT/'tools/serial_boot.py'), mode,
                '--serial', os.ttyname(device), '--console-pty', os.ttyname(console),
                '--session', str(session), '--image', str(image), '--emulator']
        if readonly: args.append('--read-only')
        launcher = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
    def stop_host():
        nonlocal launcher
        if launcher is not None:
            try: os.killpg(launcher.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            launcher.wait(timeout=10)
            launcher = None
    def check_host():
        if launcher is not None and launcher.poll() is not None:
            raise RuntimeError('launcher exited '+str(launcher.returncode))
    console_io = Console(terminal, a.out/'console.bin', check_host)
    output = console_io.output
    expect = console_io.expect
    def command(text, marker=None, timeout=180):
        data = console_io.command(text, marker, timeout)
        case(text)
        return data
    def reset_boot(name, image, readonly=False):
        stop_host()
        os.write(commands,b'R')
        time.sleep(.1)
        session=a.out/name
        start('boot',session,image,readonly)
        expect(b'A>')
        case(name+' boot')
        return session
    try:
        session=a.out/'session'
        start('boot',session)
        expect(b'A>');case('serial boot')
        time.sleep(1)
        basic_console(command)
        if a.suite=='full':
            file_utilities(command, session/'disk.img', initial_files,
                           lambda: os.write(commands,b'F'),
                           lambda: case('corrupted disk reply recovered'))
            command('P1715TST W',b'P1715TEST WRITE PASS',300)
            patterned_file(session/'disk.img')
            case('independent patterned-file verification')
            command('P1715TST W',b'P1715TEST COLLISION FAIL')
            stop_host();time.sleep(2)
            start('attach',session)
            deadline=time.monotonic()+10
            while b'phase=netdisk' not in Path(logs[-1].name).read_bytes():
                if time.monotonic()>deadline:raise RuntimeError('attach did not become ready')
                time.sleep(.05)
            command('');case('host restart without guest reset')
            os.write(terminal,b'\x03');expect(b'A>');case('warm boot')
            # Original keyboard channel and local console remain usable.
            at=len(output)
            for ch in b'TYPE HELLO.TXT\r':
                os.write(commands,b'K\xe0');time.sleep(.02)
                os.write(commands,b'K'+bytes([ch]));time.sleep(.03)
            expect(b'Native CP/M Plus on Robotron 1715',180,at)
            expect(b'A>',180,at);case('local keyboard with mirrored output')
            cold=reset_boot('cold',session/'disk.img')
            command('P1715TST R',b'P1715TEST VERIFY PASS',300)
            command('P1715TST C',b'P1715TEST CLEAN PASS',300)
            command('ERASE NEW.TXT')
            files=inspect((cold/'disk.img').read_bytes())
            assert (0,'P1715TST.DAT') not in files and (0,'NEW.TXT') not in files
            for key,data in initial_files.items(): assert files[key].data==data,key
            case('cold persistence and verified cleanup')
        if a.suite in ('full', 'media'):
            readonly=reset_boot('readonly',original,True)
            before=sha(readonly/'disk.img')
            os.write(terminal,b'PIP BLOCKED.TXT=HELLO.TXT\r')
            expect(b'ERROR: MAKE FILE NONRECOVERABLE');assert sha(readonly/'disk.img')==before
            case('read-only rejection leaves image unchanged')
            from pattern_workload import nearly_full
            full=a.out/'full-input.img';full.write_bytes(nearly_full(original.read_bytes(),2))
            full_session=reset_boot('full',full)
            command('P1715TST W',b'P1715TEST IO FAIL',300)
            case('disk-full error')
        assert sha(original)==initial_hash
        result['complete']=True
    except Exception as exc:
        result['error']=repr(exc);print(result['error'],flush=True)
    finally:
        stop_host();emu.terminate();emu.wait(timeout=10)
        emulator_log.close()
        result['session_host_hashes'] = sorted({
            json.loads(path.read_text())['host_sha256']
            for path in a.out.glob('*/identity.json')})
        result['fault_injected'] = 'injected=1\n' in (a.out/'emulator.log').read_text()
        if a.suite == 'full' and result['complete'] and not result['fault_injected']:
            result['complete'] = False
            result['error'] = 'fault injection was not observed'
        for log in logs: log.close()
        for fd in [wire,device,terminal,console,control,commands]: os.close(fd)
        (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['complete'] else 1
if __name__=='__main__':raise SystemExit(main())
