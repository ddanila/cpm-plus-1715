#!/usr/bin/env python3
"""Headless Robotron boot/attach using Ravi and the shared native N4 host (Linux)."""
import argparse, hashlib, json, os, shutil, subprocess, time
from contextlib import ExitStack
from importlib.resources import files
from pathlib import Path
from ravi.transport import SerialTransport, LoggedTransport
from ravi.backends.robotron1715.boot import StockBoot
from ravi.backends.robotron1715.monitor import Monitor, IDENTITY

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
 image=a.image.read_bytes();platform=a.platform.read_bytes()
 if len(image)!=819200 or not 0<len(platform)<0x3600:p.error('invalid Robotron artifacts')
 source=int.from_bytes(image[133:135],'little')-0x4000
 if not 0<source<128 or image[128+source:128+source+len(platform)]!=platform:p.error('platform/image mismatch')
 if not a.host.is_file():p.error('build the shared host first')
 session=a.session.resolve();working=session/'disk.img'
 if a.mode=='boot':
  session.mkdir(parents=True,exist_ok=False);shutil.copyfile(a.image,working)
  (session/'identity.json').write_text(json.dumps(dict(machine='robotron1715',framing='9600 8O2',emulator=a.emulator,source_sha256=sha(image),platform_sha256=sha(platform),host_sha256=sha(a.host.read_bytes()),read_only=a.read_only),indent=2)+'\n')
 else:
  identity=json.loads((session/'identity.json').read_text())
  if identity['platform_sha256']!=sha(platform) or identity['source_sha256']!=sha(image) or identity['read_only']!=a.read_only:p.error('session identity mismatch')
  if working.stat().st_size!=819200:p.error('invalid session disk')
 command=[str(a.host.resolve()),'--machine','robotron1715','--resume-disk','--serial',a.serial,'--volume',str(working),'--console-pty',a.console_pty,'--log',str(session/f'host-{time.time_ns()}.log'),'--capture',str(session/f'wire-{time.time_ns()}.bin')]
 if not a.read_only:command.append('--writable')
 if a.mode=='attach':return subprocess.call(command)
 with ExitStack() as stack:
  port=stack.enter_context(SerialTransport(a.serial,9600,parity='N' if a.emulator else 'O',stop_bits=2))
  tx=stack.enter_context((session/'bootstrap-tx.bin').open('wb'));rx=stack.enter_context((session/'bootstrap-rx.bin').open('wb'))
  wire=LoggedTransport(port,rx,tx)
  boot=StockBoot(wire);boot.handshake(a.timeout)
  payload=files('ravi.backends.robotron1715').joinpath('monitor.bin').read_bytes()
  boot.upload(0x4000,payload);boot.execute(0x4000)
  monitor=Monitor(wire)
  if monitor.response()!=[IDENTITY]:raise RuntimeError('wrong monitor')
  actual=b''.join(monitor.read_memory(0x4000+i,min(256,len(payload)-i)) for i in range(0,len(payload),256))
  if actual!=payload:raise RuntimeError('monitor verification failed')
  for i in range(0,len(platform),256):monitor.write_memory(0xc000+i,platform[i:i+256])
  actual=b''.join(monitor.read_memory(0xc000+i,min(256,len(platform)-i)) for i in range(0,len(platform),256))
  if actual!=platform:raise RuntimeError('platform verification failed')
  (session/'platform-readback.bin').write_bytes(actual)
  monitor.start(0xc033)
  # No close, flush, reopen or READY read between the GO and first N4 packet.
  command+=['--serial-fd',str(port.fd)]
  return subprocess.call(command,pass_fds=(port.fd,))
if __name__=='__main__':raise SystemExit(main())
