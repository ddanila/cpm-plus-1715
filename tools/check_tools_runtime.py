#!/usr/bin/env python3
"""Execute PIPEMGR/cpmbox qualification through the production serial session."""
import argparse
import json
import os
from pathlib import Path
import pty
import subprocess
import sys
import time
import tty
from evidence import atomic_json, sources
from serial_session import ROOT, Console, digest
from cpm_session import request, status
from media import inspect, add
import io
import tarfile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True)
    p.add_argument('--image',type=Path,default=ROOT/'out/cpm-plus-1715-serial.img')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--probe',action='store_true')
    p.add_argument('--failure',choices=('full','readonly'))
    p.add_argument('--upgrade',action='store_true')
    p.add_argument('--suite',choices=('all','core','utilities','streams','binary'),default='all')
    p.add_argument('--sizes',default='0,1,127,128,129,16385,49153')
    a=p.parse_args();a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
    sizes=tuple(int(n) for n in a.sizes.split(','))
    if not sizes or any(n not in (0,1,127,128,129,257,16385,49153) for n in sizes):
        p.error('sizes must be from 0,1,127,128,129,257,16385,49153')
    if a.upgrade: a.image=ROOT/'out/cpm-plus-1715-serial-base.img'
    session=a.out/'session'; original=digest(a.image)
    payloads = {f'B{n}.BIN': bytes((i * 37 + 26) % 256 for i in range(n)) for n in (0,1,127,128,129,257,16385,49153)}
    prepared = a.image.read_bytes()
    prepared = add(prepared, 'TPA.COM', (ROOT/'build/tools/tpa.cim').read_bytes())
    if a.probe:
        prepared = add(prepared, 'PMPROBE.COM', (ROOT/'build/tools/probe.com').read_bytes(), replace=(0,'PMPROBE.COM') in inspect(prepared))
    if not a.probe and not a.upgrade:
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            member = tarfile.TarInfo('TAROUT.BIN'); member.size = 129
            tar.addfile(member, io.BytesIO(payloads['B129.BIN']))
        payloads['SAMPLE.TAR'] = archive.getvalue()
        def tar_bytes(name, data=b'x', kind=tarfile.REGTYPE):
            output=io.BytesIO()
            with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as tar:
                member=tarfile.TarInfo(name);member.size=len(data);member.type=kind
                tar.addfile(member,io.BytesIO(data))
            return output.getvalue()
        payloads['BADCHK.TAR']=b'!'+payloads['SAMPLE.TAR'][1:]
        payloads['BADNAME.TAR']=tar_bytes('TOOLONGNAME.BIN')
        payloads['BADPATH.TAR']=tar_bytes('../BAD.BIN')
        payloads['BADTYPE.TAR']=tar_bytes('LINK.BIN',b'',tarfile.SYMTYPE)
        payloads['SHORT.TAR']=tar_bytes('SHORT.BIN',bytes(129))[:600]
        payloads['LOCK.BIN']=b'KEEP THIS'
        if a.suite == 'streams': payloads['TAROUT.BIN']=payloads['B129.BIN']
        for name, data in payloads.items():
            prepared = add(prepared, name, data, exact=True, attributes='R' if name=='LOCK.BIN' else '')
    if a.failure == 'full':
        used = {b for f in inspect(prepared).values() for b in f.blocks}
        prepared = add(prepared, 'FULL.BIN', bytes((388-len(used))*2048), exact=True)
    test_image = a.out/'input.img'; test_image.write_bytes(prepared)
    result=dict(status='running',hardware_executed=False,suite=a.suite,sizes=sizes,cases=[],source_sha256=sources(),rom_sha256=digest(a.rom),image_sha256=original)
    wire,device=pty.openpty();tty.setraw(wire);tty.setraw(device)
    controls, reset_writer=os.pipe()
    emulator=client=None
    log=(a.out/'emulator.log').open('wb')
    launcher=(a.out/'launcher.log').open('wb')
    def cli(action,*args,timeout=180):
        return subprocess.run([sys.executable,str(ROOT/'tools/cpm_session.py'),action,'--session',str(session),*map(str,args)],stdout=launcher,stderr=subprocess.STDOUT,timeout=timeout,check=True)
    def case(name,action):
        action();result['cases'].append(dict(name=name,status='passed'));atomic_json(a.out/'result.json',result);print(name,'PASS',flush=True)
    try:
        emulator=subprocess.Popen([str(ROOT/'build/serial-probe'),str(a.rom.resolve()),str(wire),str(a.out/'ram.bin'),str(controls)],pass_fds=(wire,controls),stderr=log)
        cli('boot','--serial',os.ttyname(device),'--emulator','--image',test_image,'--detach',*(['--read-only'] if a.failure == 'readonly' else []))
        client,_=request(session,'attach')
        console=Console(client.fileno(),a.out/'console.bin')
        console.expect(b'[Live console; Ctrl-] d detaches]',10)
        command=lambda text, marker=None: console.command(text, marker, timeout=1800)
        def check_exact(name, expected):
            # The command returned to the prompt: all guest writes were acknowledged.
            actual=inspect((session/'disk.img').read_bytes())[(0,name)].exact_data
            assert actual == expected, (name,len(actual),len(expected))
        case('TPA before tools',lambda:command('TPA',b'TPA=9D06'))
        if a.upgrade:
            case('legacy session boots',lambda:command('TYPE HELLO.TXT',b'Native CP/M'))
            client.close();client=None;cli('stop')
            cli('snapshot','--name','before')
            cli('install-tools')
            assert json.loads((session/'identity.json').read_text())['requires_boot']
            refused=subprocess.run([sys.executable,str(ROOT/'tools/cpm_session.py'),'resume','--session',str(session),'--detach'],capture_output=True)
            assert refused.returncode and b'fresh guest boot' in refused.stderr
            case('upgrade refuses resume',lambda:None)
            os.write(reset_writer,b'R');cli('boot','--detach')
            client,_=request(session,'attach');console=Console(client.fileno(),a.out/'upgraded-console.bin')
            console.expect(b'[Live console; Ctrl-] d detaches]',10)
            case('upgraded tools run after fresh boot',lambda:command('CAT HELLO.TXT | CAT',b'Native CP/M'))
            client.close();client=None;cli('stop')
            cli('restore','--name','before')
            assert (0,'CAT.COM') not in inspect((session/'disk.img').read_bytes())
            os.write(reset_writer,b'R');cli('boot','--detach')
            client,_=request(session,'attach');console=Console(client.fileno(),a.out/'restored-console.bin')
            console.expect(b'[Live console; Ctrl-] d detaches]',10)
            case('rollback boots original environment',lambda:command('TYPE HELLO.TXT',b'Native CP/M'))
        elif a.failure:
            for text in ('CAT /B B129.BIN | CAL 11 2026', 'CAT HELLO.TXT > FAIL.TXT'):
                output=command(text,b'PIPEMGR: I/O failed')
                assert b'November' not in output, output
                case(a.failure+' disk cancels '+text,lambda:None)
            case('usable prompt after disk error',lambda:command('TYPE HELLO.TXT',b'Native CP/M'))
            case('disk error restores TPA',lambda:command('TPA',b'TPA=9D06'))
        elif a.suite == 'binary':
            for n in sizes:
                case('binary pipe '+str(n),lambda n=n:command(f'CAT /B B{n}.BIN | CAT /B > C{n}.BIN'))
                case('exact bytes '+str(n),lambda n=n:check_exact(f'C{n}.BIN',payloads[f'B{n}.BIN']))
            case('binary pipes restore TPA',lambda:command('TPA',b'TPA=9D06'))
            client.close();client=None;cli('stop')
            files=inspect((session/'disk.img').read_bytes())
            for n in sizes:
                assert files[(0,f'C{n}.BIN')].exact_data == payloads[f'B{n}.BIN']
            assert not any(f.name in ('PIPEIN.$$$','PIPEOUT.$$$') for f in files.values())
            result['cases'].append(dict(name='post-stop exact bytes and temporary cleanup',status='passed'))
        elif a.probe:
            case('RSX direct execution',lambda:command('PMPROBE',b'RSX PROBE OK'))
            case('RSX three-stage pipe',lambda:command('PMPROBE | PMPROBE R | PMPROBE R',b'RSX PROBE OK'))
            case('RSX redirection',lambda:command('PMPROBE > RSX.TXT'))
            case('RSX redirected input',lambda:command('PMPROBE R < RSX.TXT',b'RSX PROBE OK'))
            case('RSX cleanup and normal utility',lambda:command('TYPE HELLO.TXT',b'Native CP/M'))
            case('RSX warm boot',console.warm_boot)
            case('RSX after warm boot',lambda:command('PMPROBE',b'RSX PROBE OK'))
            case('RSX chain restores TPA',lambda:command('TPA',b'TPA=9D06'))
        else:
            if a.suite != 'streams':
                case('binary pipe 257 (all byte values)',lambda:command('CAT /B B257.BIN | CAT /B > C257.BIN'))
                case('all byte values preserved',lambda:check_exact('C257.BIN',payloads['B257.BIN']))
                case('binary tar pipeline',lambda:command('CAT /B SAMPLE.TAR | UNTAR /V - A:',b'Extracting A:TAROUT.BIN'))
                case('extracted bytes preserved',lambda:check_exact('TAROUT.BIN',payloads['B129.BIN']))
            for name, text, marker in [
                ('CAT text','CAT HELLO.TXT',b'Native CP/M'),
                ('CAL','CAL 11 2026',b'2026'),
                ('LS','LS HELLO.TXT',b'hello.txt'),
                ('FIND A only','FIND HELLO.TXT',b'A:hello.txt'),
                ('DU','DU HELLO.TXT',b'128 bytes'),
                ('HEXDUMP binary','HEXDUMP B129.BIN',b'1A 3F 64 89'),
                ('CP binary','CP B129.BIN COPIED.BIN',None),
                ('MV','MV COPIED.BIN MOVED.BIN',None),
                ('text pipeline','CAT HELLO.TXT | CAT | CAT',b'Native CP/M'),
                ('redirect','CAT HELLO.TXT > TEXT.TXT',None),
                ('append','CAT HELLO.TXT >> TEXT.TXT',None),
                ('redirected input','CAT < TEXT.TXT',b'Native CP/M'),
                ('HEXDUMP stdin','CAT /B B129.BIN | HEXDUMP',b'1A 3F 64 89'),
                ('paging suppressed in pipes','LS /L /P | CAT /P',b'hello.txt'),
                ('CAL leap year','CAL /M 2 2024',b'29'),
            ]:
                utility = name in ('CAT text','CAL','LS','FIND A only','DU','HEXDUMP binary','CP binary','MV')
                if (a.suite == 'utilities' and not utility) or (a.suite == 'streams' and utility): continue
                case(name,lambda text=text,marker=marker:command(text,marker))
            for n in (sizes if a.suite == 'all' else ()):
                case('binary pipe '+str(n),lambda n=n:command(f'CAT /B B{n}.BIN | CAT /B > C{n}.BIN'))
            if a.suite != 'utilities':
                def cancelled(text, marker):
                    output=command(text+' | CAL 11 2026',marker)
                    assert b'November' not in output, output
                case('failed stage cancels chain',lambda:cancelled('CAT MISSING.TXT',b'File not found'))
                case('stderr redirection',lambda:command('CAT MISSING.TXT >& ERR.TXT'))
                case('redirected stderr is readable',lambda:command('CAT ERR.TXT',b'File not found'))
                for filename, marker in [('BADCHK.TAR',b'checksum failure'),('BADNAME.TAR',b'not 8.3'),
                                         ('BADPATH.TAR',b'not 8.3'),('BADTYPE.TAR',b'Unsupported tar'),
                                         ('SHORT.TAR',b'Truncated tar data'),('SAMPLE.TAR',b'destination exists')]:
                    case('tar rejects '+filename,lambda filename=filename,marker=marker:cancelled('UNTAR '+filename,marker))
                case('read-only destination',lambda:cancelled('CP B129.BIN LOCK.BIN',b'LOCK.BIN:'))
                case('missing next command',lambda:cancelled('CAT HELLO.TXT | NOEXIST',None))
                case('prompt after missing command',lambda:command('TPA',b'TPA=9D06'))
                case('stderr pipe cancellation',lambda:cancelled('CAT MISSING.TXT |& CAT',None))
                case('pipe to legacy consumer',lambda:command('CAT HELLO.TXT | PIP LEGACY.TXT=CON:'))
                def interrupt_pipeline():
                    at=len(console.output)
                    hostlog=next((session/'runs').glob('*/host-0.log'))
                    writes=hostlog.read_bytes().count(b'media write')
                    os.write(console.fd,b'CAT /B B49153.BIN | CAL 11 2026\r')
                    console.expect(b'CAT /B B49153.BIN | CAL 11 2026',30,at)
                    # Inject only after pipeline output has started reaching the drive.
                    until=time.monotonic()+180
                    while hostlog.read_bytes().count(b'media write') < writes+3:
                        if time.monotonic()>until: raise TimeoutError('pipeline never began writing')
                        time.sleep(.1)
                    os.write(console.fd,b'\x03')
                    output=console.expect(b'A>',600,at)
                    assert b'November' not in output,output
                case('Ctrl-C cancels remaining stages',interrupt_pipeline)
            case('TPA after tools',lambda:command('TPA',b'TPA=9D06'))
            case('warm boot',console.warm_boot)
            case('normal utility after tools',lambda:command('TYPE HELLO.TXT',b'Native CP/M'))
            client.close();client=None
            cli('stop')
            files = inspect((session/'disk.img').read_bytes())
            for n in (tuple(set(sizes+(257,))) if a.suite == 'all' else (() if a.suite == 'streams' else (257,))):
                assert files[(0,f'C{n}.BIN')].exact_data == payloads[f'B{n}.BIN'], n
            if a.suite != 'utilities':
                assert b'File not found' in files[(0,'ERR.TXT')].exact_data
                assert files[(0,'TEXT.TXT')].exact_data == b'Native CP/M Plus on Robotron 1715\r\n'*2
                assert files[(0,'LEGACY.TXT')].data.startswith(b'Native CP/M Plus on Robotron 1715\r\n')
            assert files[(0,'LOCK.BIN')].exact_data == b'KEEP THIS'
            assert not any(f.name in ('PIPEIN.$$$','PIPEOUT.$$$') for f in files.values())
            if a.suite != 'streams':
                assert files[(0,'MOVED.BIN')].exact_data == payloads['B129.BIN']
            assert files[(0,'TAROUT.BIN')].exact_data == payloads['B129.BIN']
            result['cases'].append(dict(name='independent exact byte comparison',status='passed'))
        assert digest(a.image)==original
        assert sources()==result['source_sha256'], 'sources changed during qualification'
        result.update(status='passed',complete=True)
    except Exception as exc:
        result.update(status='failed',complete=False,error=repr(exc));print(repr(exc),flush=True)
    finally:
        if client is not None:client.close()
        try:
            if (session/'identity.json').exists() and status(session).get('live'):cli('stop')
        except Exception as exc:result.update(status='failed',cleanup_error=repr(exc))
        if emulator is not None and emulator.poll() is None:emulator.terminate();emulator.wait(timeout=10)
        log.close();launcher.close();os.close(wire);os.close(device);os.close(controls);os.close(reset_writer)
        result['source_unchanged']=digest(a.image)==original
        atomic_json(a.out/'result.json',result)
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
