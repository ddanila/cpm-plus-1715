#!/usr/bin/env python3
"""MIT: deterministic fresh classic-1715 media, no historical disk template."""
from pathlib import Path
import sys, struct, zipfile, hashlib, json
ROOT=Path(__file__).resolve().parents[1]
def put(disk,name,data,block):
    stem,ext=name.split('.')
    name=(stem.ljust(8)+ext.ljust(3)).encode('ascii')
    records=(len(data)+127)//128
    for extent in range((records+127)//128):
        slot=next(i for i in range(20480,24576,32) if disk[i]==0xe5)
        chunk=data[extent*16384:(extent+1)*16384]
        e=bytearray(32);e[1:12]=name;e[12]=extent&31;e[14]=extent>>5;e[15]=(len(chunk)+127)//128
        for j in range((len(chunk)+2047)//2048):
            assert 2<=block<390
            e[16+2*j:18+2*j]=struct.pack('<H',block)
            part=chunk[j*2048:(j+1)*2048];off=20480+block*2048
            disk[off:off+len(part)]=part;block+=1
        disk[slot:slot+32]=e
    return block

def image():
    disk=bytearray([0xe5])*819200
    for path,expected in json.loads((ROOT/'third_party/inputs.json').read_text()).items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    platform=(ROOT/'build/platform.cim').read_bytes()
    assert len(platform)<0x3700
    # Original 4000h bootstrap copies the resident services, then enters loader.
    stage=bytes.fromhex('f331003f2117401100c0')+struct.pack('<BH',1,len(platform))+bytes.fromhex('edb0c333c0')
    # Point the copy source immediately after the generated bootstrap.
    stage=bytearray(stage);stage[5:7]=struct.pack('<H',0x4000+len(stage))
    payload=bytes(stage)+platform
    count=(len(payload)+127)//128
    header=bytearray(128);header[:6]=bytes.fromhex('03f000000100')
    header[9:11]=struct.pack('<H',0x4000);header[12:14]=struct.pack('<H',0x4000)
    header[14:16]=struct.pack('<H',count);header[16]=255
    for off in (100,108,116):header[off:off+8]=bytes([80,5,3,27,3,1,1,0])
    assert len(payload)+128<=20480
    disk[:20480]=bytes(20480);disk[:128]=header;disk[128:128+len(payload)]=payload
    block=put(disk,'CPM3.SYS',(ROOT/'build/cpm3.sys').read_bytes(),2)
    block=put(disk,'CCP.COM',(ROOT/'third_party/cpm3/ccp.com').read_bytes(),block)
    archive=ROOT/'third_party/cpm3/releases/cpm3bin_unix-20260607.zip'
    with zipfile.ZipFile(archive) as z:
        for name in ('dir','type','pip','erase','rename','show','set','submit'):
            block=put(disk,name.upper()+'.COM',z.read(name+'.com'),block)
    block=put(disk,'HELLO.TXT',b'Native CP/M Plus on Robotron 1715\r\n\x1a',block)
    block=put(disk,'TEST.SUB',b'DIR HELLO.TXT\r\nTYPE HELLO.TXT\r\n\x1a',block)
    out=ROOT/'out';out.mkdir(exist_ok=True)
    (out/'cpm-plus-1715.img').write_bytes(disk)
    print('built',len(disk),'bytes; bootstrap',len(payload),'bytes')
if __name__=='__main__':image()
