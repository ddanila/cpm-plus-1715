#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute CP/M 3 through the unchanged Z80/bus seam; inspect exported media."""
import argparse, hashlib, json, os, subprocess, sys, signal, uuid
from datetime import datetime, timezone
from evidence import sources as fingerprint, outputs, atomic_json
from media import inspect, add, name_bytes
from boot_cases import cases as boot_cases
from pathlib import Path
from pattern_workload import fixture, replace_program, record, read_file, nearly_full
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def files(data):
    return {name_bytes(f.name): f.data for f in inspect(data).values() if f.user==0}

def execute(command, settings, dest, timeout=1800):
    with (dest/'stdout.log').open('w') as stdout, (dest/'stderr.log').open('w') as stderr:
        child=subprocess.Popen(command, env=settings, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code=child.wait(timeout=timeout)
        except BaseException:
            if child.poll() is None: os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
            raise
    return code, (dest/'stdout.log').read_text(), (dest/'stderr.log').read_text()

def main():
    ap=argparse.ArgumentParser()
    for n in ['binary','rom','out']:ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--backend',choices=['native','firmware'],required=True)
    ap.add_argument('--suite',choices=['base','storage','faults','extra','boot','smoke','all'],default='all')
    ap.add_argument('--report',type=Path,required=True)
    a=ap.parse_args()
    # --out is a run root; every invocation owns an immutable unique directory.
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    a.out=a.out/run_id; a.out.mkdir(parents=True,exist_ok=False)
    print('run directory:',a.out,flush=True)
    provenance=json.loads(Path(str(a.binary)+'.json').read_text())
    deps=json.loads((ROOT/'dependencies.json').read_text())
    assert provenance['backend']==a.backend and provenance['dependencies']==deps
    assert provenance['binary_sha256']==sha(a.binary.read_bytes())
    rom_hash=sha(a.rom.read_bytes())
    fixture_hash=sha((ROOT/'build/test.rom').read_bytes())
    assert rom_hash in (fixture_hash,'51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01'), 'unknown ROM profile'
    rom_profile='public-fixture' if rom_hash==fixture_hash else 'stock-reference'
    built=outputs()
    base=(ROOT/'out/cpm-plus-1715.img').read_bytes();results=[]
    sources=fingerprint()
    env={k:v for k,v in os.environ.items() if not k.startswith('PICO1715_')}
    env.update(PICO1715_TIMED='0',PICO1715_KEY_START='30000000',PICO1715_COMMAND_GAP='100000000')
    def run(name,data,commands,markers,cycles=160000000,mode=None,extra=None,unchanged=False,faults=False):
        source=a.out/(name+'.img');source.write_bytes(data)
        dest=a.out/name;dest.mkdir();settings=env|{'PICO1715_CYCLES':str(cycles)}|(extra or {})
        if name in ['boot-dir','cold-read','cold-delete','indexed-extents','indexed-cold','corruption-negative','disk-full','disk-full-cold','write-protect','missing-system','bad-system-header','bad-system-payload','utilities','multi-warmboot']:
            settings['PICO1715_STOP_TEXT']=('CPM1715 UTILITIES COMPLETE' if name=='utilities' else markers[0] if name!='boot-dir' else 'HELLO    TXT')
        if markers and name not in ('keyboard-warmboot','erase','reset-write','set-system-attributes'):
            settings.setdefault('PICO1715_STOP_TEXT',markers[-1] if name=='multi-random-user' else markers[0])
        code,stdout,stderr=execute([str(a.binary.resolve()),str(a.rom.resolve()),str(source.resolve()),str(dest.resolve()),commands,*([mode] if mode else [])],settings,dest)
        assert code in (0,1),(name,code,stderr)
        assert len((dest/'ram.bin').read_bytes())==65536
        assert len((dest/'disk.img').read_bytes())==819200
        stats=json.loads(stdout);screen=(dest/'screen.txt').read_text();output=(dest/'disk.img').read_bytes()
        # Legacy runner exit means observed 0204h ROM handoff; it is not an
        # OS success signal for the fixture. Screen and media qualify success.
        assert code==(0 if stats['rom_handoff_cycle'] else 1),(name,code,stats)
        if name in ('absent','crc-fault'):
            assert 'CP/M Plus 3.1' not in screen and 'A>' not in screen,(name,screen)
            assert stats['writes']==0 and stats['keyboard_bytes']==0
            if name=='absent': assert stats['fields']==0 and stats['bytes']==0
            else: assert stats['fields']>0 and stats['bytes']>0
            if rom_profile=='public-fixture': assert 'CP/M 3 boot error' in screen
        assert all(m in screen for m in markers),(name,screen,stats)
        assert source.read_bytes()==data
        if commands and name!='reset-write':assert stats['keyboard_bytes']==len(commands)*2,(name,stats)
        if unchanged:assert output==data,name
        if name not in {n for n,_,good in boot_cases(base) if not good}: inspect(output)
        if not faults:assert all(stats[k]==0 for k in ['overruns','underflows','drops','tx_overruns','tx_underruns','sio_errors','rejected_writes']),(name,stats)
        if name=='multi-warmboot':assert screen.rstrip().endswith('A>'),screen
        results.append(dict(case=name,status='passed',exit_status=code,commands=commands,media_mode=mode or 'writable',markers=markers,settings={k:v for k,v in settings.items() if k.startswith('PICO1715_')},stats=stats,input_sha256=sha(data),output_sha256=sha(output),screen=screen,stderr=stderr))
        print(name,'PASS',flush=True)
        return output
    if a.suite=='smoke':
        run('boot-dir',base,'DIR\r',['CP/M Plus 3.1 - Robotron 1715','HELLO    TXT','A>'],unchanged=True)
        run('crc-fault',base,'',[],cycles=30000000,extra={'PICO1715_CORRUPT_CRC':'1'},unchanged=True,faults=True)
    if a.suite in ('boot','all'):
        flagged=run('set-system-attributes',base,'SET CPM3.SYS [RO SYS]\r',['A>'],cycles=180000000)
        sysfile=inspect(flagged)[0,'CPM3.SYS']
        assert 'R' in sysfile.attributes and 'S' in sysfile.attributes
        run('attributed-cold-boot',flagged,'DIR\r',['HELLO    TXT'],unchanged=True)
        for name,data,good in boot_cases(base):
            run(name,data,'DIR\r' if good else '',['HELLO    TXT' if good else 'CP/M 3 boot error'],cycles=100000000,unchanged=True)
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
        d=add(base,'RELIABLE.COM',(ROOT/'build/reliability-test.cim').read_bytes())
        out=run('multi-random-user',d,'RELIABLE\r',['CPM1715 MULTI RANDOM USER OK'],cycles=300000000)
        content=inspect(out)
        assert content[1,'USERTEST.BIN'].data==bytes(range(256))*2
        assert (0,'USERTEST.BIN') not in content
        for key,value in inspect(d).items(): assert content[key].data==value.data
        run('user-cold',out,'USER 1\rDIR USERTEST.BIN\r',['USERTEST BIN'],cycles=250000000,unchanged=True)
        d=add(base,'DIRFULL.COM',(ROOT/'build/directory-test.cim').read_bytes())
        for i in range(128-sum(len(f.slots) for f in inspect(d).values())): d=add(d,f'E{i}',b'')
        run('directory-full',d,'DIRFULL\r',['CPM1715 DIRECTORY FULL OK'],unchanged=True)
        data=b''.join(record(i,83) for i in range(256))
        d=add(base,'LARGE.BIN',data)
        d=add(d,'BIGDONE.TXT',b'CPM1715 LARGE COPY OK\r\n\x1a')
        d=add(d,'LARGERUN.SUB',b'PIP BIGCOPY.BIN=LARGE.BIN\r\nDIR BIGCOPY.BIN\r\nTYPE BIGDONE.TXT\r\n\x1a')
        out=run('large-pip',d,'SUBMIT LARGERUN\r',['CPM1715 LARGE COPY OK','BIGCOPY  BIN'],cycles=1000000000)
        assert inspect(out)[0,'BIGCOPY.BIN'].data==data
        for key,value in inspect(d).items(): assert inspect(out)[key].data==value.data
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
        recovered=run('reset-write',base,'PIP COPY.TXT=HELLO.TXT\r',['CP/M Plus 3.1 - Robotron 1715'],cycles=250000000,extra={'PICO1715_RESET_PHASE':'2'})
        assert results[-1]['stats']['resets']==1 and results[-1]['stats']['reset_image_unchanged']==1
        assert files(recovered)[b'COPY    TXT']==files(base)[b'HELLO   TXT']
        for key,value in inspect(base).items(): assert inspect(recovered)[key].data==value.data
        run('reset-cold-read',recovered,'TYPE COPY.TXT\r',['Native CP/M Plus on Robotron 1715'],unchanged=True)
    from runtime_cases import expected_cases
    assert {r['case'] for r in results}==expected_cases(a.suite)
    assert fingerprint()==sources, 'sources changed during qualification'
    assert outputs()==built and sha(a.binary.read_bytes())==provenance['binary_sha256'] and sha(a.rom.read_bytes())==rom_hash
    report=dict(source_sha256=sources,output_sha256=built,dependencies=deps,schema=2,status='passed',run_id=run_id,
        hardware_executed=False,backend=a.backend,suite=a.suite,rom_profile=rom_profile,rom_sha256=rom_hash,
        binary_sha256=provenance['binary_sha256'],image_sha256=sha(base),cases=results)
    atomic_json(a.out/'report.json',report)
    atomic_json(a.report,report)
if __name__=='__main__':
    def stop(signum, frame): raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM,stop)
    main()
