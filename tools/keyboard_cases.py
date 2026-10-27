# SPDX-License-Identifier: MIT
"""Independent byte arrivals during guest BIOS disk operations."""
import json
from pathlib import Path
from media import add,inspect
ROOT=Path(__file__).resolve().parents[1]
COMMAND=b'KBDTEST\r'

def pairs(data,start=40000000,period=101000):
    return [(start+i*period+offset,byte) for i,c in enumerate(data) for offset,byte in ((0,0xe0),(1000,c))]

def fixture(base,mode,wanted):
    code=bytearray((ROOT/'build/keyboard-test.cim').read_bytes())
    code[3]=mode;code[4:6]=wanted.to_bytes(2,'little')
    d=add(base,'KBDTEST.COM',bytes(code))
    pattern=bytes(range(256))*64
    d=add(d,'KBDDATA.BIN',pattern,start_block=380)
    return add(d,'KBDOUT.BIN',bytes(256),start_block=388)

def qualify(base,run,results,root,backend,only=None):
    info=json.loads((ROOT/'build/keyboard-map.json').read_text())
    symbols=info['symbols']
    data=bytes([65+i%26 for i in range(60)])+b'\r\x08\x03\x09'
    cases=[]
    for phase in (0,10000,80000):
        cases.append((f'keyboard-phase-{phase}',0,64,data,pairs(data,start=40000000+phase),0,{}))
    wrapped=bytes(33+i%90 for i in range(256))
    cases.append(('keyboard-wrap',2,256,wrapped,pairs(wrapped),0,{}))
    excess=bytes(33+i%90 for i in range(160));recovery=b'RECOVERED INPUT!'
    assert len(recovery)==16
    cases.append(('keyboard-overflow',1,160,excess[:128]+recovery,pairs(excess)+pairs(recovery,start=65000000),32,{}))
    # Orphan data, duplicate prefix, NUL, and a prefix separated from its byte.
    split=[(40000000,85),(40100000,224),(40101000,224),(40102000,65),
           (40200000,224),(40201000,0),(40300000,224),(40500000,66)]
    cases.append(('keyboard-prefix',0,2,b'AB',split,0,{}))
    cases.append(('keyboard-warm-preserve',3,len(b'TYPE HELLO.TXT\r'),None,pairs(b'TYPE HELLO.TXT\r'),0,{}))
    cases.append(('keyboard-reset-clock',0,64,data,[(0,99)]+pairs(data),0,{'PICO1715_RESET_PHASE':'1'}))
    for name,mode,wanted,expected,events,drops,extra in cases:
        if only is not None and name not in only:continue
        d=fixture(base,mode,wanted)
        schedule=sorted(pairs(COMMAND,start=30000000)+events)
        extra=extra|{'PICO1715_KEY_SERVICE_PC':str(symbols['keyservice']), 'PICO1715_KEY_SERVICE_START':'40000000', 'PICO1715_KEY_SERVICE_END':str(max(t for t,_ in events)+101000)}
        marker='Native CP/M Plus on Robotron 1715' if mode==3 else 'CPM1715 ASYNC KEYBOARD OK'
        out=run(name,d,'',[marker],cycles=120000000,extra=extra,events=schedule)
        stats=results[-1]['stats']
        disabled=1 if name=='keyboard-reset-clock' else 0
        assert stats['key_attempted']==len(schedule) and stats['key_pending']==0 and stats['key_late']==0,(name,stats)
        assert stats['key_rejected']==disabled and stats['key_disabled']==disabled and stats['key_full']==0,(name,stats)
        if disabled:assert stats['resets']==1
        ram=(root/name/'ram.bin').read_bytes()
        word=lambda label:int.from_bytes(ram[symbols[label]:symbols[label]+2],'little')
        assert word('keydrops')==drops,(name,word('keydrops'))
        assert ram[symbols['keycount']]==0,(name,ram[symbols['keycount']])
        assert stats['key_service_visits']>0
        results[-1]['keyboard_diagnostics']={n:word(n) for n in ('keycalls','keydecoded','keydrops')}
        before,after=inspect(d),inspect(out)
        for key,value in before.items():
            if key!=(0,'KBDOUT.BIN'):assert after[key].data==value.data,(name,key)
        if expected is not None:assert after[0,'KBDOUT.BIN'].data==expected.ljust(256,b'\0'),(name,after[0,'KBDOUT.BIN'].data)
        else:assert out==d
        assert stats['writes']>0 and stats['steps']>0,(name,stats)

def characterize(base,run,results,root):
    info=json.loads((ROOT/'build/keyboard-map.json').read_text());s=info['symbols']
    data=bytes(65+i%26 for i in range(64))
    for period in (50000,20000):
        name=f'keyboard-rate-{period}'
        d=fixture(base,0,len(data));events=pairs(COMMAND,start=30000000)+pairs(data,period=period)
        out=run(name,d,'',[],cycles=80000000,faults=True,events=events,
                extra={'PICO1715_KEY_SERVICE_PC':str(s['keyservice']),'PICO1715_KEY_SERVICE_START':'40000000', 'PICO1715_KEY_SERVICE_END':str(max(t for t,_ in events)+101000)})
        stats=results[-1]['stats']
        assert stats['key_attempted']==len(events) and stats['key_late']==stats['key_pending']==stats['key_disabled']==0
        assert all(stats[k]==0 for k in ('overruns','underflows','drops','tx_overruns','tx_underruns','rejected_writes'))
        before,after=inspect(d),inspect(out)
        for key,value in before.items():
            if key!=(0,'KBDOUT.BIN'):assert after[key].data==value.data
        if stats['key_rejected']:
            assert stats['key_full']==stats['key_rejected'] and stats['sio_errors']!=0
            assert 'CPM1715 ASYNC KEYBOARD OK' not in results[-1]['screen']
            assert after[0,'KBDOUT.BIN'].data==bytes(256)
            outcome='receiver overflow; outside qualified envelope'
        else:
            assert after[0,'KBDOUT.BIN'].data==data.ljust(256,b'\0')
            outcome='exact receipt at this phase; characterization only'
        results[-1]['rate_characterization']=dict(period_clocks=period,outcome=outcome)
