#!/usr/bin/env python3
"""MIT. Exercise the production W4 auto launcher with an actual ROM/model."""
import argparse,json,os,pty,signal,subprocess,sys,tty
from pathlib import Path
from importlib.resources import files
from serial_session import Console
from media import inspect
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--baud',type=int,default=62400);p.add_argument('--nonbanked',action='store_true');p.add_argument('--stock',action='store_true');a=p.parse_args()
 a.out.mkdir(parents=True);session=a.out/'session';wire,device=pty.openpty();terminal,console=pty.openpty()
 for fd in (wire,device,terminal,console):tty.setraw(fd)
 elog=(a.out/'emulator.log').open('wb');hlog=(a.out/'host.log').open('wb');host=None;emu=None
 env=dict(os.environ,PYTHONPATH=str(ROOT.parent/'ravi/src'),JH_TEST_PTY_UNPACED='1')
 rom=Path(str(files('ravi.backends.robotron1715w').joinpath('rom-w4.bin')))
 def model():
  command=[str(ROOT/'build/wm-probe'),str(rom),str(wire),str(a.out/'ram.bin'),str(a.baud)]
  if a.stock:command=[str(ROOT/'build/serial-probe'),str(ROOT/'build/serial-test.rom'),str(wire),str(a.out/'ram.bin')]
  return subprocess.Popen(command,pass_fds=(wire,),stderr=elog)
 args=[sys.executable,str(ROOT/'tools/serial_wm_w4.py'),'auto','--host',str(a.host),'--serial',os.ttyname(device),'--console-pty',os.ttyname(console),'--session',str(session),'--baud',str(a.baud)]+(['--nonbanked'] if a.nonbanked else [])
 if a.stock:args=[sys.executable,str(ROOT/'tools/serial_boot.py'),'auto','--host',str(a.host),'--serial',os.ttyname(device),'--console-pty',os.ttyname(console),'--session',str(session)]
 if a.stock and os.ttyname(device).startswith('/dev/pts/'):args.append('--emulator')
 def launch():return subprocess.Popen(args,stdout=hlog,stderr=hlog,env=env,start_new_session=True)
 def stop():
  if host and host.poll() is None:os.killpg(host.pid,signal.SIGTERM);host.wait(timeout=10)
 def check():
  if host.poll() is not None or emu.poll() is not None:raise RuntimeError('child exited; inspect logs')
 c=Console(terminal,a.out/'console.bin',check);report=dict(complete=False,hardware_executed=False,cases=[])
 def passed(name):report['cases'].append(name);print(name,'PASS',flush=True)
 try:
  emu=model();host=launch();c.expect(b'A>',start=0,timeout=180);passed('auto cold boot')
  assert b'Robotron' in c.command('TYPE HELLO.TXT')
  c.command('PIP COPY.TXT=HELLO.TXT');f=inspect((session/'disk.img').read_bytes());assert f[(0,'COPY.TXT')].data==f[(0,'HELLO.TXT')].data;passed('verified session write')
  stop();host=launch();assert b'Robotron' in c.command('TYPE COPY.TXT');passed('auto host restart')
  for index in range(2):
   at=len(c.output);emu.terminate();emu.wait(timeout=10);emu=model();c.expect(b'A>',start=at,timeout=180)
   assert b'Robotron' in c.command('TYPE COPY.TXT');passed('target power cycle '+str(index+1))
  report['complete']=True
 finally:
  stop()
  if emu and emu.poll() is None:emu.terminate();emu.wait(timeout=10)
  for fd in (wire,device,terminal,console):os.close(fd)
  elog.close();hlog.close();(a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
