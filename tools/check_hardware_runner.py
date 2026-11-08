#!/usr/bin/env python3
"""Qualify the physical runner using a timed serial endpoint with no reset controls."""
import argparse
import json
import os
import pty
import signal
import subprocess
import sys
import time
import tty
from pathlib import Path
from evidence import atomic_json
from serial_session import ROOT, digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--scenario', choices=['normal', 'boot-timeout', 'disconnect', 'interrupt'], default='normal')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    master, slave = pty.openpty()
    tty.setraw(master); tty.setraw(slave)
    emulator = runner = None
    emulog = (a.out/'emulator.log').open('wb')
    runlog = (a.out/'runner.log').open('wb')
    result = dict(scenario=a.scenario, passed=False, hardware_executed=False,
                  rom_sha256=digest(a.rom), emulator_sha256=digest(ROOT/'build/serial-probe'))
    try:
        if a.scenario != 'boot-timeout':
            # Deliberately no control descriptor: no reset, keyboard or fault injection.
            emulator = subprocess.Popen([str(ROOT/'build/serial-probe'), str(a.rom),
                str(master), str(a.out/'ram.bin')], pass_fds=(master,), stderr=emulog)
        args = [sys.executable, str(ROOT/'tools/check_serial_hardware.py'),
                '--serial', os.ttyname(slave), '--board', 'emulator-no-reset',
                '--out', str(a.out/'campaign'), '--emulator']
        if a.scenario == 'boot-timeout': args += ['--boot-timeout', '.5']
        runner = subprocess.Popen(args, stdout=runlog, stderr=subprocess.STDOUT)
        if a.scenario in ('disconnect', 'interrupt'):
            until = time.monotonic()+180
            while time.monotonic()<until:
                report = a.out/'campaign/result.json'
                if report.exists():
                    progress = json.loads(report.read_text())
                    if a.scenario == 'interrupt' and progress['phase'] == 'verified serial boot':
                        runner.send_signal(signal.SIGTERM)
                        break
                    if a.scenario == 'disconnect' and any(c['status']=='passed' for c in progress['cases']):
                        emulator.terminate(); emulator.wait(timeout=10)
                        os.close(master); master=-1
                        break
                if runner.poll() is not None: raise RuntimeError('runner exited before injection')
                time.sleep(.05)
            else: raise TimeoutError('injection milestone missing')
        code = runner.wait(timeout=3700 if a.scenario=='normal' else 90)
        campaign = json.loads((a.out/'campaign/result.json').read_text())
        expected = 0 if a.scenario=='normal' else 130 if a.scenario=='interrupt' else 1
        assert code == expected, (code, campaign)
        assert campaign['hardware_executed'] is False
        if a.scenario == 'normal':
            assert campaign['supported_suite_passed'] and len(campaign['cases']) == 11
        else:
            assert not campaign['complete'] and campaign['manual_power_cycle_required']
        assert campaign['source_unchanged']
        result.update(passed=True, exit_code=code, campaign=campaign)
    except Exception as exc:
        result['error'] = repr(exc)
        print(result['error'], flush=True)
    finally:
        if runner is not None and runner.poll() is None:
            runner.terminate(); runner.wait(timeout=15)
        if emulator is not None and emulator.poll() is None:
            emulator.terminate(); emulator.wait(timeout=10)
        emulog.close(); runlog.close()
        if master>=0: os.close(master)
        os.close(slave)
        atomic_json(a.out/'result.json', result)
    return 0 if result['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
