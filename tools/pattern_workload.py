"""Original BDOS workload with indexed records and multi-extent validation."""
from classic_workload import install
DIRECTORY=20480; BLOCK=2048; BLOCKS=390

def record(index,seed=83):
    data=bytearray((seed+index+j)&255 for j in range(128));data[1]=index>>8
    return bytes(data)

def program(records=256,seed=83,verify_only=False,expect_full=False):
    if not 1<=records<=4096 or not 0<=seed<=255:raise ValueError('invalid workload bounds')
    b=bytearray();labels={};fix=[]
    def emit(*x):b.extend(x)
    def label(n):labels[n]=256+len(b)
    def addr(op,n):emit(op);fix.append((len(b),n));emit(0,0)
    def call(n,ptr=None):
        if ptr is not None:emit(17,ptr&255,ptr>>8)
        emit(14,n,205,5,0)
    def fail_ff():emit(254,255);addr(202,'fail')
    def close():call(16,0x700);fail_ff()
    def next_record(loop):
        emit(3,120,254,records>>8);addr(194,loop);emit(121,254,records&255);addr(194,loop)
    if not verify_only:
        call(26,0x800);call(22,0x700);fail_ff();emit(1,0,0)
        label('write');emit(197);addr(205,'pattern');call(21,0x700);emit(193)
        if expect_full:emit(254,2);addr(202,'full')
        emit(183);addr(194,'fail');next_record('write')
        if expect_full:addr(195,'fail')
        close();call(13)
        for offset in (12,14,32):emit(175,50,offset,7)
    call(15,0x700);fail_ff();call(26,0x900);emit(1,0,0)
    label('read');emit(197);addr(205,'pattern');call(20,0x700);emit(193,183);addr(194,'fail')
    emit(197,33,0,8,17,0,9,6,128)
    label('compare');emit(26,190);addr(194,'fail');emit(35,19,5);addr(194,'compare');emit(193);next_record('read')
    close();addr(17,'ok');addr(195,'print')
    label('full');emit(237,67,0xf0,6);close();addr(17,'full_ok');addr(195,'print')
    label('fail');addr(17,'bad')
    label('print');call(9);emit(195,0,0)
    label('pattern');emit(80,121,198,seed,33,0,8,6,128)
    label('fill');emit(119,35,60,16,251,122,50,1,8,201)
    for name,text in [('ok',b'PICO PATTERN OK\r\n$'),('bad',b'PICO PATTERN FAILED\r\n$'),('full_ok',b'PICO DISK FULL OK\r\n$')]:label(name);b.extend(text)
    for at,name in fix:b[at:at+2]=labels[name].to_bytes(2,'little')
    assert len(b)<0x5f0
    b.extend(bytes(0x600-len(b)));b.extend(b'\0PICOTESTTXT'+bytes(24))
    return bytes(b)

def fixture(image,records=256,seed=83,verify_only=False,expect_full=False):
    # Allocate through the existing checked installer, preserving all old files.
    disk=bytearray(install(image,block=None)[0]);code=program(records,seed,verify_only,expect_full)
    offset=next(i for i in range(DIRECTORY,DIRECTORY+4096,32) if disk[i:i+12]==b'\0PICOTESTCOM')
    block=int.from_bytes(disk[offset+16:offset+18],'little');disk[offset+15]=(len(code)+127)//128
    disk[DIRECTORY+block*BLOCK:DIRECTORY+block*BLOCK+len(code)]=code
    return bytes(disk)

def replace_program(image,**kwargs):
    disk=bytearray(image);code=program(**kwargs)
    offset=next(i for i in range(DIRECTORY,DIRECTORY+4096,32) if disk[i:i+12]==b'\0PICOTESTCOM')
    block=int.from_bytes(disk[offset+16:offset+18],'little')
    assert (len(code)+127)//128==disk[offset+15]
    disk[DIRECTORY+block*BLOCK:DIRECTORY+block*BLOCK+len(code)]=code
    return bytes(disk)

def read_file(image,name=b'PICOTESTTXT'):
    entries=[image[i:i+32] for i in range(DIRECTORY,DIRECTORY+4096,32) if image[i]==0 and bytes(c&127 for c in image[i+1:i+12])==name]
    if not entries:raise ValueError('file missing')
    result=bytearray();used=set()
    for ordinal,e in enumerate(sorted(entries,key=lambda e:(e[14]&63)*32+(e[12]&31))):
        if (e[14]&63)*32+(e[12]&31)!=ordinal or e[15]>128:raise ValueError('invalid extent sequence')
        if ordinal<len(entries)-1 and e[15]!=128:raise ValueError('short intermediate extent')
        blocks=[int.from_bytes(e[j:j+2],'little') for j in range(16,32,2)];count=(e[15]+15)//16
        for block in blocks[:count]:
            if not 2<=block<BLOCKS or block in used:raise ValueError('invalid allocation')
            used.add(block)
        data=b''.join(image[DIRECTORY+k*BLOCK:DIRECTORY+(k+1)*BLOCK] for k in blocks[:count])
        result.extend(data[:e[15]*128])
    return bytes(result)

def nearly_full(image,free_blocks=10):
    disk=bytearray(image);entries=[disk[i:i+32] for i in range(DIRECTORY,DIRECTORY+4096,32)]
    used={0,1}
    for e in entries:
        if e[0]<16:used.update(int.from_bytes(e[j:j+2],'little') for j in range(16,32,2))
    free=[i for i in range(2,BLOCKS) if i not in used]
    if len(free)<free_blocks:raise ValueError('insufficient free space')
    reserve=free[free_blocks:];slots=[i for i,e in enumerate(entries) if e[0]==229]
    if len(slots)<(len(reserve)+7)//8:raise ValueError('directory full')
    for n,at in enumerate(range(0,len(reserve),8)):
        blocks=reserve[at:at+8];e=bytearray(32);e[:12]=b'\0'+f'FILL{n:04d}BIN'.encode();e[15]=len(blocks)*16
        for j,block in enumerate(blocks):e[16+j*2:18+j*2]=block.to_bytes(2,'little')
        offset=DIRECTORY+slots[n]*32;disk[offset:offset+32]=e
    return bytes(disk)
