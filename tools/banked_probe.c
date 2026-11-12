/* SPDX-License-Identifier: MIT
 * Instruction-executed BIOS tests. Direct setup is confined to this unit probe;
 * W4 integration separately exercises ROM upload and the filesystem loader. */
#include "machines/robotron1715m/robotron.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static robotron m;
static unsigned entry;
static void invoke(unsigned vector, unsigned af, unsigned bc, unsigned de, unsigned hl) {
  m.cpu.cpu.af=af; m.cpu.cpu.bc=bc; m.cpu.cpu.de=de; m.cpu.cpu.hl=hl;
  m.cpu.cpu.sp=0xf680;
  m.ram[0xf680]=0x80; m.ram[0xf681]=0xf7; m.ram[0xf780]=0x76;
  m.cpu.pins=z80_prefetch(&m.cpu.cpu,(uint16_t)(entry+3*vector));
  for(unsigned n=0;n<3000000;n++) {
    dac_z80_tick(&m.cpu,0,0);
    if(m.cpu.pins & Z80_HALT) return;
  }
  fprintf(stderr,"BIOS %u timed out pc=%04x bank=%02x\n",vector,m.cpu.cpu.pc,m.bank);
  abort();
}
static void select(unsigned bank) {
  invoke(27,bank<<8,0x5678,0x9abc,0xdef0);
  assert(m.bank==(bank+1)*17);
  assert(m.cpu.cpu.bc==0x5678 && m.cpu.cpu.de==0x9abc && m.cpu.cpu.hl==0xdef0);
}
static void io(unsigned write,unsigned track,unsigned sector,unsigned address,unsigned bank) {
  invoke(10,0,track,0,0); invoke(11,0,sector,0,0);
  invoke(12,0,address,0,0); invoke(28,bank<<8,0,0,0);
  invoke(write ? 14 : 13,0,0,0,0);
}
int main(int argc,char **argv) {
  assert(argc==2);
  robotron_init(&m);
  for(unsigned b=1;b<=4;b++) for(unsigned pg=0;pg<16;pg++)
    m.prom[128+b*16+pg]=(pg>=12?1:1u<<(b-1))^15;
  FILE *f=fopen(argv[1],"rb"); assert(f);
  unsigned char header[256],record[128];
  assert(fread(header,1,256,f)==256);
  entry=header[4]+256*header[5];
  for(unsigned seg=0;seg<2;seg++) {
    unsigned top=header[seg*2]*256, bytes=header[seg*2+1]*256;
    for(unsigned n=0;n<bytes;n+=128) {
      assert(fread(record,1,128,f)==128);
      memcpy(m.ram+top-n-128,record,128);
    }
  }
  assert(fgetc(f)==EOF); fclose(f);
  select(0); select(1); select(0);
  /* One-shot interbank move, returned pointers, zero count, common boundary. */
  for(unsigned i=0;i<256;i++) m.ram[65536+0x4000+i]=(unsigned char)(i^0x5a);
  invoke(29,0,0x0001,0,0);
  invoke(25,0,256,0x4000,0x5000);
  assert(m.bank==0x11 && m.cpu.cpu.hl==0x5100 && m.cpu.cpu.de==0x4100);
  assert(!memcmp(m.ram+0x5000,m.ram+65536+0x4000,256));
  m.ram[0x4000]=0xa7;
  invoke(25,0,1,0x4000,0x5100); assert(m.ram[0x5100]==0xa7);
  invoke(29,0,0x0100,0,0); invoke(25,0,0,0x4000,0x5000);
  assert(m.bank==0x11 && m.cpu.cpu.hl==0x5000 && m.cpu.cpu.de==0x4000);
  m.ram[0xbfff]=0x61; m.ram[0xc000]=0x62;
  invoke(29,0,0x0100,0,0); invoke(25,0,2,0xbfff,0xbfff);
  assert(m.ram[65536+0xbfff]==0x61 && m.ram[0xc000]==0x62 && m.bank==0x11);
  /* RAM disk first/last records and both sides of the bank boundary. */
  invoke(9,0,1,0,0); assert(m.cpu.cpu.hl);
  const unsigned records[]={0,383,384,767};
  for(unsigned bank=0;bank<2;bank++) for(unsigned k=0;k<4;k++) {
    unsigned r=records[k];
    for(unsigned i=0;i<128;i++) m.ram[bank*65536+0x6000+i]=(unsigned char)(i+r+k);
    io(1,r/8,r%8+1,0x6000,bank); assert(m.cpu.cpu.a==0 && m.bank==0x11);
    unsigned physical=(2+r/384)*65536+(r%384)*128;
    assert(!memcmp(m.ram+physical,m.ram+bank*65536+0x6000,128));
    memset(m.ram+bank*65536+0x6100,0,128);
    io(0,r/8,r%8+1,0x6100,bank); assert(m.cpu.cpu.a==0 && m.bank==0x11);
    assert(!memcmp(m.ram+physical,m.ram+bank*65536+0x6100,128));
  }
  io(0,96,1,0x6000,0); assert(m.cpu.cpu.a==1 && m.bank==0x11);
  io(0,0,0,0x6000,0); assert(m.cpu.cpu.a==1 && m.bank==0x11);
  io(0,0,9,0x6000,0); assert(m.cpu.cpu.a==1 && m.bank==0x11);
  invoke(9,0,2,0,0); assert(m.cpu.cpu.hl==0);
  puts("BANKED-BIOS: PASS (mapping, copy, DMA, RAM-disk boundaries, errors)");
  return 0;
}
