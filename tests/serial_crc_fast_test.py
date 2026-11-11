"""Execute the actual Z80 CRC routine over every state and input byte."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAC = Path(os.environ.get('DAC', ROOT.parent / 'dac-emulation'))

@unittest.skipUnless((DAC/'common/cpu/z80.c').exists(), 'external DAC Z80 core required')
class FastCrcTest(unittest.TestCase):
    def test_exhaustive_state_and_register_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            assembly = '''        org 1000h
        jp N3CRC
ROMNETDISK equ 1
SHARED_SERIAL equ 1
N3Z80TABLE equ 1
ROMNETSTATEBASE equ 0a000h
serial_begin:
serial_finish:
serial_tx:
serial_rx: ret
        .8080
'''+f'        include "{ROOT}/third_party/juku-common/platform/netdisk-v3.asm"\n        .z80\n        include "{ROOT}/src/serial-crc-table.asm"\n'
            (d/'test.asm').write_text(assembly)
            subprocess.run([str(ROOT/'build/bin/zmac'), '--zmac', '-o', str(d/'test.cim'), str(d/'test.asm')], check=True)
            (d/'test.c').write_text(r'''
#include "common/cpu/z80.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char mem[65536];
static uint8_t rd(void *u,uint16_t a){(void)u;return mem[a];}
static void wr(void *u,uint16_t a,uint8_t b){(void)u;mem[a]=b;}
static unsigned crc(unsigned c,unsigned b){c^=b;for(int i=0;i<8;i++)c=(c>>1)^((c&1)?0xa001:0);return c;}
int main(int argc,char **argv){
 assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);
 assert(fread(mem+0x1000,1,0x4000,f)>0);fclose(f);mem[0]=0x76;
 dac_z80 c;dac_z80_bus bus={.read=rd,.write=wr};unsigned long long max=0;
 /* All 16,777,216 state/byte combinations; real opcodes, independent reference. */
 for(unsigned state=0;state<65536;state++)for(unsigned b=0;b<256;b++){
  dac_z80_init(&c,bus);c.cpu.de=state;c.cpu.a=b;c.cpu.hl=0xabcd;c.cpu.bc=0x9876;
  c.cpu.sp=0xf000;mem[0xf000]=0;mem[0xf001]=0;c.pins=z80_prefetch(&c.cpu,0x1000);
  do {dac_z80_tick(&c,0,0);assert(c.cycles<160);}while(!(c.pins&Z80_HALT));
  assert(c.cpu.de==crc(state,b));assert(c.cpu.hl==0xabcd);assert(c.cpu.bc==0x9876);assert(c.cpu.sp==0xf002);
  if(c.cycles>max)max=c.cycles;
 }
 printf("CRC: 16777216 state/byte cases PASS, max %llu clocks including entry JP and HALT\n",max);
}
''')
            subprocess.run(['cc','-std=c11','-O2','-I'+str(DAC),str(d/'test.c'),str(DAC/'common/cpu/z80.c'),'-o',str(d/'test')],check=True)
            subprocess.run([str(d/'test'),str(d/'test.cim')],check=True)
