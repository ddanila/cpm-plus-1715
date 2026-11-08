#!/usr/bin/env python3
"""Headless Robotron boot/attach using Ravi and the shared native N4 host (Linux)."""
import argparse, hashlib, json, os, shutil, subprocess, time
from contextlib import ExitStack
from serial_session import bootstrap, host_command, validate_artifacts, positive
from pathlib import Path
from ravi.transport import SerialTransport

ROOT=Path(__file__).resolve().parents[1]
def sha(data): return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['boot','attach'])
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
 if a.emulator and not a.serial.startswith('/dev/pts/'):p.error('--emulator requires a PTY')
 if a.timeout<=0:p.error('positive timeout required')
 positive(a.timeout)
 image,platform=validate_artifacts(a.image,a.platform)
 if not a.host.is_file():p.error('build the shared host first')
 session=a.session.resolve();working=session/'disk.img'
 if a.mode=='boot':
  session.mkdir(parents=True,exist_ok=False);shutil.copyfile(a.image,working)
  (session/'identity.json').write_text(json.dumps(dict(machine='robotron1715',framing='9600 8O2',emulator=a.emulator,source_sha256=sha(image),platform_sha256=sha(platform),host_sha256=sha(a.host.read_bytes()),read_only=a.read_only),indent=2)+'\n')
 else:
  identity=json.loads((session/'identity.json').read_text())
  if identity['platform_sha256']!=sha(platform) or identity['source_sha256']!=sha(image) or identity['read_only']!=a.read_only:p.error('session identity mismatch')
  if working.stat().st_size!=819200:p.error('invalid session disk')
 command=host_command(a.host,a.serial,working,a.console_pty,session/f'host-{time.time_ns()}.log',session/f'wire-{time.time_ns()}.bin',a.read_only)
 if a.mode=='attach':return subprocess.call(command)
 with ExitStack() as stack:
  port=stack.enter_context(SerialTransport(a.serial,9600,parity='N' if a.emulator else 'O',stop_bits=2))
  bootstrap(port,platform,session,a.timeout)
  # No close, flush, reopen or READY read between the GO and first N4 packet.
  command+=['--serial-fd',str(port.fd)]
  return subprocess.call(command,pass_fds=(port.fd,))
if __name__=='__main__':raise SystemExit(main())
