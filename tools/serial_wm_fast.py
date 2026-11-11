#!/usr/bin/env python3
"""MIT. Experimental PC001 W2/PL2303HXD 41600 runtime; verified RAM monitor required."""
import argparse,json,os,shutil,signal,subprocess,time
from pathlib import Path
from ravi.transport import SerialTransport,LoggedTransport
from ravi.backends.robotron1715w.host import Monitor
from serial_session import lock_session,validate_artifacts
from serial_wm import digest,W2_ID,host_command,ROOT
from wm_usb_rate import USBRate,check_device
import fcntl,struct

SHIM=bytes.fromhex('f33e47d309d30a3e03d309d30aaf d30f3e04d30f3e44d30fc35001')

class MonitorUploadTransport:
 """Pace the RAM-less W2 CRC parser; runtime uses the unpaced descriptor."""
 def __init__(self,port):self.port=port
 def read(self,size,timeout):return self.port.read(size,timeout)
 def write(self,data):
  for byte in data:
   self.port.write(bytes([byte]));time.sleep(0.0005)

def configure(port,usb,rate):
 fcntl.ioctl(port.fd,0x80085402,struct.pack('Q',rate))
 return usb.set(rate)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('mode',choices=['boot','attach'])
 p.add_argument('--serial',required=True)
 p.add_argument('--session',type=Path,required=True)
 p.add_argument('--console-pty',required=True)
 p.add_argument('--host',type=Path,required=True)
 p.add_argument('--monitor-baud',type=int,choices=[9600,41600],default=9600,help='Already qualified W2 x16 monitor rate; NOT cold W2 x1')
 p.add_argument('--image',type=Path,default=ROOT/'out/cpm-plus-1715-wm-fast.img')
 p.add_argument('--platform',type=Path,default=ROOT/'build/platform-wm-fast.cim')
 p.add_argument('--read-only',action='store_true')
 a=p.parse_args();a.test_corrupt_read_reply_once=False
 device=check_device(a.serial)
 _,code=validate_artifacts(a.image,a.platform)
 # Exact initialization sequence distinguishes the fast platform from 1200 images.
 if bytes.fromhex('3e47d309d30a3e03d309d30a') not in code:raise ValueError('Platform lacks counter-mode divisor 3')
 session=a.session.resolve()
 identity=dict(machine='robotron1715w',format='41600 8N1 x16',host_baud=41666,usb=device,image_sha256=digest(a.image),platform_sha256=digest(a.platform),host_sha256=digest(a.host),read_only=a.read_only)
 if a.mode=='boot':
  session.mkdir(parents=True,exist_ok=False);shutil.copyfile(a.image,session/'disk.img')
  (session/'identity.json').write_text(json.dumps(identity,indent=2))
 else:
  old=json.loads((session/'identity.json').read_text())
  if any(old.get(k)!=v for k,v in identity.items()):raise ValueError('Session identity mismatch')
  if (session/'disk.img').stat().st_size!=819200:raise ValueError('Invalid disk size')
 with lock_session(session/'session.lock'),SerialTransport(a.serial,9600,parity='N',stop_bits=1,exclusive=True) as port:
  usb=USBRate();child=None;report={'complete':False,'device':device,'monitor_byte_delay_ms':0.5}
  try:
   if a.mode=='boot':
    with (session/'bootstrap-rx.bin').open('wb') as rx,(session/'bootstrap-tx.bin').open('wb') as tx:
     wire=LoggedTransport(MonitorUploadTransport(port),rx,tx)
     if a.monitor_baud==41600:report['rate']=configure(port,usb,41600)
     m=Monitor(wire,5);info=m.identify()
     if info['build_id']!=W2_ID:raise ValueError('Unexpected W2 ROM')
     report['rom']=info
     if a.monitor_baud==9600:
      m.write_memory(0x8000,SHIM);m.start(0x8000)
      report['rate']=configure(port,usb,41600)
      m=Monitor(wire,5);assert m.identify()['build_id']==W2_ID
     m.write_memory(0xc000,code);actual=m.read_memory(0xc000,len(code))
     (session/'platform-readback.bin').write_bytes(actual)
     if actual!=code:raise ValueError('Platform readback mismatch')
     m.start(0xc033);report['complete']=True
     report['events']=m.events
   else:report['rate']=configure(port,usb,41600)
   command=host_command(a,session,port.fd)+['--disk-baud','41600']
   report['command']=command
   (session/f'launch-{time.time_ns()}.json').write_text(json.dumps(report,indent=2))
   child=subprocess.Popen(command,pass_fds=(port.fd,))
   def stop(signum,frame):raise KeyboardInterrupt
   old=signal.signal(signal.SIGTERM,stop)
   try:return child.wait()
   except KeyboardInterrupt:return 130
   finally:signal.signal(signal.SIGTERM,old)
  finally:
   if child is not None and child.poll() is None:
    child.terminate()
    try:child.wait(timeout=10)
    except subprocess.TimeoutExpired:child.kill();child.wait()
   (session/'latest-launch.json').write_text(json.dumps(report,indent=2))
   usb.close()
if __name__=='__main__':raise SystemExit(main())
