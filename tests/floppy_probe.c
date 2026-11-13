/* SPDX-License-Identifier: MIT. Real Z80 driver against timed FDC/drive model. */
#include "machines/robotron1715m/robotron.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static robotron m;
static unsigned char disks[2][819200];
static unsigned call(unsigned vector,unsigned a,unsigned drive,unsigned track,unsigned record) {
 m.cpu.cpu.af=a<<8; m.cpu.cpu.bc=drive; m.cpu.cpu.hl=track; m.cpu.cpu.de=record; m.cpu.cpu.ix=0xf800;
 m.cpu.cpu.sp=0xf680; m.ram[0xf680]=0x80; m.ram[0xf681]=0xf7; m.ram[0xf780]=0x76;
 m.cpu.pins=z80_prefetch(&m.cpu.cpu,0xd000+vector*3);
 for(unsigned n=0;n<30000000;n++) { robotron_run(&m,1); if(m.cpu.pins&Z80_HALT) { printf("call %u drive %u track %u -> %u FDC %02x %02x %02x bytes=%u phase=%u\n",vector,drive,track,m.cpu.cpu.a,m.fdc.result[0],m.fdc.result[1],m.fdc.result[2],m.fdc.data_pos,m.fdc.phase); fflush(stdout); return m.cpu.cpu.a; } }
 fprintf(stderr,"timeout vector %u pc=%04x phase=%u pos=%u\n",vector,m.cpu.cpu.pc,m.fdc.phase,m.fdc.data_pos); assert(0); return 1;
}
int main(int argc,char **argv) {
 assert(argc==2 || argc==3); robotron_init(&m);
 for(unsigned b=1;b<=4;b++) for(unsigned p=0;p<16;p++) m.prom[128+b*16+p]=(p>=12?1:1u<<(b-1))^15;
 m.bank=0x22;
 FILE *f=fopen(argv[1],"rb"); assert(f); assert(fread(m.ram+0xd000,1,0xc00,f)>0); assert(feof(f)); fclose(f);
 memset(disks,0x17,sizeof disks);
 assert(!robotron_disk(&m,dac_memory_storage(disks[0],819200,1),1));
 assert(!robotron_disk_unit(&m,1,dac_memory_storage(disks[1],819200,1),1));
 assert(!call(0,0,0,0,0));
 assert(!m.fdc.non_dma);
 /* Controller counter and physical head can disagree on entry. */
 m.fdc.physical[0]=79; m.fdc.cylinder[0]=0;
 assert(!call(1,0,2,0,1));
 assert(m.fdc.physical[0]==0);
 assert(!call(5,0,2,0,0));
 assert(call(2,0,2,0,1)); /* ordinary writes locked */
 assert(call(3,0,2,0,0)); /* format token required */
 assert(!call(3,0xa5,2,0,0));
 for(unsigned i=0;i<5120;i++) assert(disks[0][i]==0xe5);
 assert(disks[0][5120]==0x17 && disks[1][0]==0x17);
 assert(!call(1,0,2,0,1));
 for(unsigned i=0;i<128;i++) assert(m.ram[0xf800+i]==0xe5);
 assert(!call(4,0xa5,2,0,0));
 for(unsigned i=0;i<128;i++) m.ram[0xf800+i]=(unsigned char)(i*73+19);
 assert(!call(2,0,2,0,2));
 assert(disks[0][0]==0xe5 && disks[0][256]==0xe5);
 for(unsigned i=0;i<128;i++) assert(disks[0][128+i]==(unsigned char)(i*73+19));
 assert(call(2,0,3,0,1)); /* C unlock must not unlock D */
 assert(!call(3,0xa5,3,159,0));
 assert(disks[1][159*5120]==0xe5 && disks[1][158*5120]==0x17);
 assert(!call(4,0,0,0,0)); assert(call(2,0,2,0,1));
 /* Reject malformed positions and unavailable/protected media without writing. */
 assert(call(1,0,2,160,1));
 assert(call(1,0,2,0,0));
 assert(call(1,0,2,0,41));
 assert(call(1,0,4,0,1));
 assert(!robotron_disk(&m,dac_memory_storage(disks[0],819200,0),0));
 unsigned char saved=disks[0][128];
 assert(call(3,0xa5,2,0,0));
 assert(disks[0][128]==saved && !m.dma.enabled);
 assert(!robotron_disk(&m,dac_memory_storage(disks[0],819200,1),1));
 robotron_drive_door(&m,0,1);
 assert(call(5,0,2,0,0));
 robotron_drive_door(&m,0,0);
 assert(!call(7,0,0,0,0));
 assert(m.motor==0);
 if(argc==3) {
  /* Execute formatter command parsing and all 160 tracks against timed FDC. */
  unsigned char other[819200]; memcpy(other,disks[1],sizeof other);
  FILE *com=fopen(argv[2],"rb"); assert(com);
  assert(fread(m.ram+65536+0x100,1,0x3000,com)>0); assert(feof(com)); fclose(com);
  m.ram[65536]=0x76; m.ram[65536+5]=0xc9;
  m.ram[65536+0x80]=8; memcpy(m.ram+65536+0x81," C ERASE",9);
  m.cpu.cpu.sp=0xb900; m.cpu.pins=z80_prefetch(&m.cpu.cpu,0x100);
  int bdos=0,pass=0,halted=0;
  for(unsigned n=0;n<2000000000u;n++) {
   if(m.cpu.cpu.pc==5 && !bdos) {
    bdos=1;
    if(m.cpu.cpu.c==9) {
     char line[256]; unsigned used=0,p=m.cpu.cpu.de;
     while(m.ram[65536+p]!='$') { assert(used<255 && p<0xc000); line[used++]=(char)m.ram[65536+p++]; }
     line[used]=0; fputs(line,stdout); fflush(stdout);
     if(strstr(line,"FORMAT PASS")) pass=1;
    }
   }
   if(m.cpu.cpu.pc!=5) bdos=0;
   robotron_run(&m,1);
   if(m.cpu.pins&Z80_HALT) { halted=1; break; }
  }
  assert(halted && pass);
  for(unsigned i=0;i<sizeof disks[0];i++) assert(disks[0][i]==0xe5);
  assert(!memcmp(other,disks[1],sizeof other));
  puts("FORMATTER PASS: command parser, all 160 tracks/800 sectors, verify, other disk unchanged");
 }
 puts("FLOPPY PASS: probe, token guard, format, RMW, two drives, last cylinder/head, write isolation");
}
