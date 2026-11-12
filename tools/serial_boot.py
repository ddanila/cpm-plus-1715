#!/usr/bin/env python3
"""Headless Robotron boot/attach using Ravi and the shared native N4 host (Linux)."""
import argparse, hashlib, json, os, shutil, subprocess, time, sys
from contextlib import ExitStack
from serial_session import bootstrap, host_command, validate_artifacts, positive
from pathlib import Path
from ravi.transport import SerialTransport

ROOT=Path(__file__).resolve().parents[1]
def sha(data): return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['boot','attach','auto'])
 p.add_argument('--serial',required=True)
 p.add_argument('--image',type=Path,default=ROOT/'out/cpm-plus-1715-serial.img')
 p.add_argument('--platform',type=Path,default=ROOT/'build/platform-serial.cim')
 p.add_argument('--host',type=Path,default=ROOT.parent/'8080-cosim/build/jukuhost')
 p.add_argument('--session',type=Path,required=True)
 p.add_argument('--console-pty',required=True)
 p.add_argument('--emulator',action='store_true',help='PTY only; logical 9600 8O2, no physical parity')
 p.add_argument('--timeout',type=float,default=120)
 p.add_argument('--read-only',action='store_true')
 a=p.parse_args()
 if a.mode=='auto':
  from shared_host import load
  load(a.host)
  from jh_recovery import preflight
  preflight(a.host)
 if a.emulator and not a.serial.startswith('/dev/pts/'):p.error('--emulator requires a PTY')
 if a.timeout<=0:p.error('positive timeout required')
 positive(a.timeout)
 image,platform=validate_artifacts(a.image,a.platform)
 if not a.host.is_file():p.error('build the shared host first')
 session=a.session.resolve();working=session/'disk.img'
 if a.mode=='boot' or (a.mode=='auto' and not session.exists()):
  session.mkdir(parents=True,exist_ok=False);shutil.copyfile(a.image,working)
  (session/'identity.json').write_text(json.dumps(dict(machine='robotron1715',framing='9600 8O2',emulator=a.emulator,source_sha256=sha(image),platform_sha256=sha(platform),host_sha256=sha(a.host.read_bytes()),read_only=a.read_only),indent=2)+'\n')
 else:
  identity=json.loads((session/'identity.json').read_text())
  if identity.get('host_sha256')!=sha(a.host.read_bytes()):p.error('host identity mismatch')
  if identity['platform_sha256']!=sha(platform) or identity['source_sha256']!=sha(image) or identity['read_only']!=a.read_only:p.error('session identity mismatch')
  if working.stat().st_size!=819200:p.error('invalid session disk')
 command=host_command(a.host,a.serial,working,a.console_pty,session/f'host-{time.time_ns()}.log',session/f'wire-{time.time_ns()}.bin',a.read_only)
 if a.mode=='attach':return subprocess.call(command)
 with ExitStack() as stack:
  if a.mode=='auto':
   from serial_session import lock_session
   stack.enter_context(lock_session(session/'session.lock'))
  port=stack.enter_context(SerialTransport(a.serial,9600,parity='N' if a.emulator else 'O',stop_bits=2))
  if a.mode=='auto':
   from shared_host import load
   load(a.host)
   from jh_recovery import arguments
   command+=arguments(a.host,session,ROOT/'tools/recovery_profile.py',dict(baud=9600,parity='O',stop_bits=2),
       [a.image,a.platform],serial=a.serial,options=dict(profile='stock1715',platform=str(a.platform.resolve())))
  else:bootstrap(port,platform,session,a.timeout)
  # No close, flush, reopen or READY read between the GO and first N4 packet.
  command+=['--serial-fd',str(port.fd)]
  if a.mode=='auto':
   from jh_recovery import run_child
   return run_child(command,port.fd)
  return subprocess.call(command,pass_fds=(port.fd,))
if __name__=='__main__':raise SystemExit(main())
