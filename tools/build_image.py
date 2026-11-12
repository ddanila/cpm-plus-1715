#!/usr/bin/env python3
"""MIT: deterministic fresh classic-1715 media, no historical disk template."""
from pathlib import Path
import sys, struct, zipfile, hashlib, json
ROOT=Path(__file__).resolve().parents[1]
from media import add, inspect

def put(disk,name,data,block):
    updated=add(disk,name,data,system=True,start_block=block)
    disk[:]=updated
    allocations=inspect(updated)[(0,name)].blocks
    return max(allocations,default=block-1)+1

def image(serial=False, base=False, wm=False, wm_fast=False, wm_62400=False, wm_9600=False, banked=None):
    wm = wm or wm_fast or wm_62400 or wm_9600 or bool(banked)
    disk=bytearray([0xe5])*819200
    for path,expected in json.loads((ROOT/'third_party/inputs.json').read_text()).items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    platform=b'' if banked else (ROOT/('build/platform-wm-9600.cim' if wm_9600 else 'build/platform-wm-62400.cim' if wm_62400 else 'build/platform-wm-fast.cim' if wm_fast else 'build/platform-wm.cim' if wm else 'build/platform-serial.cim' if serial else 'build/platform.cim')).read_bytes()
    if banked:
        platform=(ROOT/f"build/banked/platform-{banked}.cim").read_bytes()
        assert len(platform) <= 0x1600
    assert len(platform)<0x3600
    assert len(platform)<0x3700
    # Original 4000h bootstrap copies the resident services, then enters loader.
    stage=bytes.fromhex('f331003f2117401100c0')+struct.pack('<BH',1,len(platform))+bytes.fromhex('edb0c333c0')
    if banked:
        stage=bytearray(stage)
        stage[8:10]=struct.pack('<H',0xe000)
        stage[-2:]=struct.pack('<H',0xe033)
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
    block=put(disk,'CPM3.SYS',(ROOT/('build/banked/cpm3.sys' if banked else 'build/cpm3.sys')).read_bytes(),2)
    block=put(disk,'CCP.COM',(ROOT/'third_party/cpm3/ccp.com').read_bytes(),block)
    archive=ROOT/'third_party/cpm3/releases/cpm3bin_unix-20260607.zip'
    with zipfile.ZipFile(archive) as z:
        for name in ('dir','type','pip','erase','rename','show','set','submit'):
            block=put(disk,name.upper()+'.COM',z.read(name+'.com'),block)
    if not wm:
        block=put(disk,'P1715TST.COM',(ROOT/'build/p1715test.cim').read_bytes(),block)
    block=put(disk,'HELLO.TXT',b'Native CP/M Plus on Robotron 1715\r\n\x1a',block)
    block=put(disk,'TEST.SUB',b'DIR HELLO.TXT\r\nTYPE HELLO.TXT\r\n\x1a',block)
    out=ROOT/'out';out.mkdir(exist_ok=True)
    if serial and not wm:
        (out/'cpm-plus-1715-serial-base.img').write_bytes(disk)
        if not base:
            from tool_bundle import install
            disk, _ = install(disk)
    if not base:
        (out/(f'cpm-plus-1715-wm-banked-{banked}.img' if banked else 'cpm-plus-1715-wm-9600.img' if wm_9600 else 'cpm-plus-1715-wm-62400.img' if wm_62400 else 'cpm-plus-1715-wm-fast.img' if wm_fast else 'cpm-plus-1715-wm.img' if wm else 'cpm-plus-1715-serial.img' if serial else 'cpm-plus-1715.img')).write_bytes(disk)
    if banked:
        contract=json.loads((ROOT/'build/banked/system-map.json').read_text())
        contract.update(baud={'9600':9600,'fast':41600,'62400':62400}[banked],
            platform_sha256=hashlib.sha256(platform).hexdigest(),
            image_sha256=hashlib.sha256(disk).hexdigest())
        (ROOT/f'build/banked/platform-{banked}.json').write_text(json.dumps(contract,indent=2)+'\n')
    print('built',len(disk),'bytes; bootstrap',len(payload),'bytes')
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--serial',action='store_true')
    parser.add_argument('--base', action='store_true')
    parser.add_argument('--wm', action='store_true')
    parser.add_argument('--wm-fast', action='store_true')
    parser.add_argument('--wm-62400', action='store_true')
    parser.add_argument('--wm-9600', action='store_true')
    parser.add_argument('--banked', choices=('9600','fast','62400'))
    args = parser.parse_args()
    image(args.serial, args.base, args.wm, args.wm_fast, args.wm_62400, args.wm_9600, args.banked)
