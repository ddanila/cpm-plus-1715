/* SPDX-License-Identifier: MIT
 * Execute the real COM, including split-bank LDIR; BDOS output is a fixture.
 * Inject a video RAM readback corruption to exercise restoration on failure.
 */
#include "machines/robotron1715m/robotron.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static robotron m;
static unsigned char before[262144], chars[4096], screen[4096];
static char output[16384];
static void load(const char *name,unsigned char *to,size_t cap) {
 FILE *f=fopen(name,"rb"); assert(f); assert(fread(to,1,cap,f)>0); assert(feof(f)); fclose(f);
}
static void run(const char *com,const char *platform,int mode) {
 robotron_init(&m);
 for(unsigned b=1;b<=4;b++) for(unsigned p=0;p<16;p++)
  m.prom[128+b*16+p]=(p>=12?1:1u<<(b-1))^15;
 for(unsigned i=0;i<sizeof(m.ram);i++) m.ram[i]=(unsigned char)(i*37+(i>>13));
 for(unsigned i=0;i<4096;i++) { m.chargen[i]=(unsigned char)(i*13); m.vram[i]=(unsigned char)(i*7); }
 load(com,m.ram+65536+0x100,0x3000);
 load(platform,m.ram+0xe000,0x1700);
 if(mode==2) m.ram[0xe000]^=1;
 m.ram[65536]=0x76; m.ram[65536+5]=0xc9;
 m.bank=0x22; m.crtc_status=4; m.display_on=1;
 memcpy(before,m.ram,sizeof before); memcpy(chars,m.chargen,4096); memcpy(screen,m.vram,4096);
 m.cpu.cpu.sp=0xbef0; m.cpu.pins=z80_prefetch(&m.cpu.cpu,0x100);
 unsigned used=0; int bdos=0, injected=0, halted=0;
 for(unsigned n=0;n<12000000;n++) {
  if(mode==1 && !injected && m.video_writes>=8192 && m.bank==0x20) {
   m.vram[123]^=1; injected=1;
  }
  if(m.cpu.cpu.pc==5 && !bdos) {
   bdos=1;
   if(m.cpu.cpu.c==9) {
    unsigned p=m.cpu.cpu.de;
    while(m.ram[65536+p]!='$') { assert(used+1<sizeof output && p<0xc000); output[used++]=(char)m.ram[65536+p++]; }
   } else if(m.cpu.cpu.c==2) { assert(used+1<sizeof output); output[used++]=(char)m.cpu.cpu.e; }
  }
  if(m.cpu.cpu.pc!=5) bdos=0;
  dac_z80_tick(&m.cpu,0,0);
  if(m.cpu.pins&Z80_HALT) { halted=1; break; }
 }
 assert(halted); output[used]=0; puts(output);
 assert(strstr(output,mode==2?"VIDEO SKIP":mode==1?"VIDEO FAIL":"VIDEO RAM PASS"));
 assert(mode!=1 || injected);
 assert(!memcmp(chars,m.chargen,4096)); assert(!memcmp(screen,m.vram,4096));
 assert(m.bank==0x22 && (m.crtc_status&0x44)==4 && m.display_on);
 assert(!memcmp(before,m.ram,65536)); /* includes restored common trampoline */
 assert(!memcmp(before+131072,m.ram+131072,131072));
}
int main(int argc,char **argv) { assert(argc==3); for(int mode=0;mode<3;mode++) run(argv[1],argv[2],mode); puts("VIDEO-PROBE PASS: real instructions, failure restoration, profile guard, bank isolation"); }
