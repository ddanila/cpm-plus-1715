"""Run the shared CRC on a Z80: ADD's P/V flag differs from the Juku 8080."""
import shutil, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless((ROOT.parent/"dac-emulation/machines/robotron1715/pc1715.c").exists(), "external DAC sources required for the CPU integration test")
class SharedCrcTest(unittest.TestCase):
 def test_z80_vectors(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);assembly='''        .8080
        org 0
        jmp main
ROMNETDISK equ 1
SHARED_SERIAL equ 1
ROMNETSTATEBASE equ 0a000h
serial_begin:
serial_finish:
serial_tx:
serial_rx: ret
'''+f'        include "{ROOT}/third_party/juku-common/platform/netdisk-v3.asm"\n'+'''main: lxi sp,0f000h
        lxi d,0
        lxi h,vector
        mvi b,9
loop: push b
        mov a,m
        call N3CRC
        pop b
        inx h
        dcr b
        jnz loop
        xchg
        shld 09000h
        lxi d,0
        lxi h,reply
        mvi b,10
reply_loop: push b
        mov a,m
        call N3CRC
        pop b
        inx h
        dcr b
        jnz reply_loop
        xchg
        shld 09002h
        hlt
reply: db 044h,04ah,006h,000h,001h,004h,000h,026h,001h,000h
vector: db '123456789'
        ds 2048-$,0
'''
   (d/'crc.asm').write_text(assembly)
   subprocess.run([str(ROOT/'build/bin/zmac'),'--zmac','-o',str(d/'crc.cim'),str(d/'crc.asm')],check=True)
   (d/'run.c').write_text('''#include "machines/robotron1715/pc1715.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc,char **argv){assert(argc==2);pc1715 *m=calloc(1,sizeof(*m));pc1715_init(m);FILE *f=fopen(argv[1],"rb");assert(f);assert(fread(m->rom,1,2048,f)==2048);fclose(f);pc1715_run(m,100000);assert(m->cpu.pins&Z80_HALT);assert(m->ram[0x9000]==0x3d && m->ram[0x9001]==0xbb);assert(m->ram[0x9002]==0x9c && m->ram[0x9003]==0x02);free(m);}
''')
   dac=ROOT.parent/'dac-emulation'
   subprocess.run(['cc','-std=c11','-O2','-I'+str(dac),str(d/'run.c'),str(dac/'machines/robotron1715/pc1715.c'),str(dac/'common/cpu/z80.c'),str(dac/'common/trace/trace.c'),'-o',str(d/'run')],check=True)
   subprocess.run([str(d/'run'),str(d/'crc.cim')],check=True)
