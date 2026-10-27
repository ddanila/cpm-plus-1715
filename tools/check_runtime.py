#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute CP/M 3 through the unchanged Z80/bus seam; inspect exported media."""
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
from pattern_workload import fixture, replace_program, record, read_file, nearly_full
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def files(data):
    result={}
    for off in range(20480,24576,32):
        e=data[off:off+32]
        if e[0]!=0:continue
        name=bytes(x&127 for x in e[1:12])
        extent=e[12]+32*e[14];pieces=[]
        for j in range(16,32,2):
            b=int.from_bytes(e[j:j+2],'little')
            if b:pieces.append(data[20480+b*2048:20480+(b+1)*2048])
        result.setdefault(name,[]).append((extent,b''.join(pieces)[:e[15]*128]))
    return {k:b''.join(v for _,v in sorted(rows)) for k,rows in result.items()}
def main():
    ap=argparse.ArgumentParser()
    for n in ['binary','rom','out']:ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--backend',choices=['native','firmware'],required=True)
    ap.add_argument('--suite',choices=['base','storage','faults','extra','all'],default='all')
    ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    base=(ROOT/'out/cpm-plus-1715.img').read_bytes();results=[]
    source_files=[p for folder in ['src','tools'] for p in (ROOT/folder).glob('*') if p.is_file()]
    sources={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in source_files}
    env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
    env.update(PICO1715_TIMED='0',PICO1715_KEY_START='30000000',PICO1715_COMMAND_GAP='100000000')
    def run(name,data,commands,markers,cycles=160000000,mode=None,extra=None,unchanged=False,faults=False):
        source=a.out/(name+'.img');source.write_bytes(data)
        dest=a.out/name;dest.mkdir();settings=env|{'PICO1715_CYCLES':str(cycles)}|(extra or {})
        if name in ['boot-dir','cold-read','cold-delete','indexed-extents','indexed-cold','corruption-negative','disk-full','disk-full-cold','write-protect','missing-system','bad-system-header','bad-system-payload','utilities','multi-warmboot']:
            settings['PICO1715_STOP_TEXT']=('CPM1715 UTILITIES COMPLETE' if name=='utilities' else markers[0] if name!='boot-dir' else 'HELLO    TXT')
        r=subprocess.run([str(a.binary.resolve()),str(a.rom.resolve()),str(source.resolve()),str(dest.resolve()),commands,*([mode] if mode else [])],env=settings,text=True,capture_output=True,check=False,timeout=1800)
        assert r.returncode in [0,1],(name,r.stderr)
        assert len((dest/'ram.bin').read_bytes())==65536
        assert len((dest/'disk.img').read_bytes())==819200
        stats=json.loads(r.stdout);screen=(dest/'screen.txt').read_text();output=(dest/'disk.img').read_bytes()
        assert all(m in screen for m in markers),(name,screen,stats)
        assert source.read_bytes()==data
        if commands and name!='reset-write':assert stats['keyboard_bytes']==len(commands)*2,(name,stats)
        if unchanged:assert output==data,name
        if not faults:assert all(stats[k]==0 for k in ['overruns','underflows','drops','tx_overruns','tx_underruns','sio_errors','rejected_writes']),(name,stats)
        if name=='multi-warmboot':assert screen.rstrip().endswith('A>'),screen
        results.append(dict(case=name,markers=markers,stats=stats,input_sha256=sha(data),output_sha256=sha(output),screen=screen))
        print(name,'PASS',flush=True)
        return output
    if a.suite in ('base','all'):
        run('boot-dir',base,'DIR\r',['CP/M Plus 3.1 - Robotron 1715','HELLO    TXT','A>'],unchanged=True)
        from build_image import put
        util=bytearray(base)
        used=[int.from_bytes(util[i+j:i+j+2],'little') for i in range(20480,24576,32) if util[i]<16 for j in range(16,32,2)]
        block=put(util,'DONE.TXT',b'CPM1715 UTILITIES COMPLETE\r\n\x1a',max(used)+1)
        put(util,'RUNALL.SUB',b'PIP COPY.TXT=HELLO.TXT\r\nTYPE COPY.TXT\r\nRENAME RENAMED.TXT=COPY.TXT\r\nSHOW\r\nDIR HELLO.TXT\r\nTYPE DONE.TXT\r\n\x1a',block)
        out=run('utilities',bytes(util),'SUBMIT RUNALL\r',['Native CP/M Plus on Robotron 1715','A>DIR HELLO.TXT','A>SHOW','CPM1715 UTILITIES COMPLETE'],cycles=650000000)
        assert files(out)[b'RENAMED TXT']==files(base)[b'HELLO   TXT']
        assert b'COPY    TXT' not in files(out)
        run('cold-read',out,'TYPE RENAMED.TXT\r',['Native CP/M Plus on Robotron 1715'],unchanged=True)
        erased=run('erase',out,'ERASE RENAMED.TXT\r',['A>'],cycles=180000000)
        assert b'RENAMED TXT' not in files(erased)
        run('cold-delete',erased,'DIR RENAMED.TXT\r',['No File'],unchanged=True)
        run('keyboard-warmboot',base,'DIX\x08R\r\x03DIR\r',['HELLO    TXT'],cycles=100000000,extra={'PICO1715_COMMAND_GAP':'10000000'},unchanged=True)
    if a.suite in ('extra','all'):
        from build_image import put
        d=bytearray(base)
        used=[int.from_bytes(d[i+j:i+j+2],'little') for i in range(20480,24576,32) if d[i]<16 for j in range(16,32,2)]
        put(d,'MULTI.COM',bytes.fromhex('1112010e09cd05001e040e2ccd0500c30000')+b'MULTI RECORD SET\r\n$',max(used)+1)
        run('multi-warmboot',bytes(d),'MULTI\r',['MULTI RECORD SET'],cycles=100000000,unchanged=True)
    if a.suite in ('storage','all'):
        out=run('indexed-extents',fixture(base,256,83),'PICOTEST\r',['PICO PATTERN OK'],cycles=1000000000)
        assert read_file(out)==b''.join(record(i,83) for i in range(256))
        verify=replace_program(out,records=256,seed=83,verify_only=True)
        run('indexed-cold',verify,'PICOTEST\r',['PICO PATTERN OK'],cycles=300000000,mode='readonly',unchanged=True)
        bad=bytearray(verify);slot=next(i for i in range(20480,24576,32) if bad[i:i+12]==b'\0PICOTESTTXT')
        block=int.from_bytes(bad[slot+16:slot+18],'little');bad[20480+block*2048+40]^=1
        run('corruption-negative',bytes(bad),'PICOTEST\r',['PICO PATTERN FAILED'],cycles=180000000,mode='readonly',unchanged=True)
        full=nearly_full(fixture(base,256,83,expect_full=True),10)
        out=run('disk-full',full,'PICOTEST\r',['PICO DISK FULL OK'],cycles=1600000000)
        assert read_file(out)==b''.join(record(i) for i in range(160))
        run('disk-full-cold',replace_program(out,records=160,verify_only=True),'PICOTEST\r',['PICO PATTERN OK'],cycles=250000000,mode='readonly',unchanged=True)
    if a.suite in ('faults','all'):
        run('write-protect',base,'PIP COPY.TXT=HELLO.TXT\r',['ERROR:'],mode='readonly',unchanged=True)
        missing=bytearray(base);missing[20480]=229
        run('missing-system',bytes(missing),'',['CP/M 3 boot error'],cycles=80000000,unchanged=True)
        corrupt=bytearray(base);corrupt[20480+2*2048]=0
        run('bad-system-header',bytes(corrupt),'',['CP/M 3 boot error'],cycles=80000000,unchanged=True)
        # No media may stop in the stock ROM, before our diagnostic code exists.
        corrupt=bytearray(base);corrupt[20480+2*2048+400]^=1
        run('bad-system-payload',bytes(corrupt),'',['CP/M 3 boot error'],cycles=80000000,unchanged=True)
        run('absent',base,'',[],cycles=15000000,mode='absent',unchanged=True)
        run('crc-fault',base,'',[],cycles=30000000,extra={'PICO1715_CORRUPT_CRC':'1'},unchanged=True,faults=True)
        run('reset-write',base,'PIP COPY.TXT=HELLO.TXT\r',['CP/M Plus 3.1 - Robotron 1715'],cycles=250000000,extra={'PICO1715_RESET_PHASE':'2'})
        assert results[-1]['stats']['resets']==1 and results[-1]['stats']['reset_image_unchanged']==1
    assert all(sha((ROOT/p).read_bytes())==h for p,h in sources.items()),'sources changed during qualification'
    report=dict(source_sha256=sources,schema=1,hardware_executed=False,backend=a.backend,suite=a.suite,rom_sha256=sha(a.rom.read_bytes()),binary_sha256=sha(a.binary.read_bytes()),image_sha256=sha(base),cases=results)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
