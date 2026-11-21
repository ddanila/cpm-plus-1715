/* MIT. Execute production PC1715 initialization/local console on DAC's raster.
 * Synthetic glyphs are an independent wiring fixture, not a stock font dump. */
#include "machines/robotron1715/pc1715.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static pc1715 m;
static unsigned char glyphs[4096];
static void enter(unsigned pc) {
  m.cpu.cpu.sp=0xf700;
  m.ram[0xf700]=0xf0; m.ram[0xf701]=0x3f;
  m.ram[0x3ff0]=0x76;
  m.cpu.pins=z80_prefetch(&m.cpu.cpu,pc);
}
static void call(unsigned pc) {
  enter(pc);
  unsigned n;
  for(n=0;n<2000000 && !(m.cpu.pins&Z80_HALT);n++) pc1715_run(&m,1);
  assert(n<2000000);
}
static void check_raster(void) {
  pc1715_run(&m,PC1715_CLOCK_HZ/20);
  assert(m.video.running && m.video.latch==0x3e && !m.video.underruns);
  for(unsigned row=0;row<24;row++) for(unsigned col=0;col<80;col++)
    for(unsigned y=0;y<12;y++) for(unsigned x=0;x<8;x++) {
      unsigned c=m.ram[0xf800+row*80+col];
      assert(c<128);
      unsigned bits=glyphs[y*128+c];
      if(col==m.video.reg[4] && row==m.video.reg[5]) bits^=255;
      unsigned expected=(bits&(128>>x))?0xffaaaaaa:0xff000000;
      assert(m.video.pixels[(row*12+y)*640+col*8+x]==expected);
    }
}
int main(int argc,char **argv) {
  assert(argc==7);
  unsigned init=strtoul(argv[2],0,16), boundary=strtoul(argv[3],0,16);
  unsigned localout=strtoul(argv[4],0,16), legacy=atoi(argv[5]);
  pc1715_init(&m);pc1715_onboard_enable(&m);m.rom_enabled=0;
  for(unsigned c=1;c<128;c++) for(unsigned y=0;y<12;y++) {
    glyphs[y*128+c]=c==32?0:(unsigned char)((c*13+y*7)|0x80);
    glyphs[2048+y*128+c]=~glyphs[y*128+c];
  }
  assert(!pc1715_video_load(&m,glyphs,sizeof glyphs));
  FILE *f=fopen(argv[1],"rb");assert(f);
  size_t n=fread(m.ram+0xc000,1,0x3600,f);assert(n>0 && feof(f));fclose(f);
  /* Dirty prior latch/registers must be replaced, not inherited from ROM. */
  m.video.latch=0x40;m.video.reg[0]=0;m.video.reg[1]=0;
  enter(init);
  for(n=0;n<2000000 && m.cpu.cpu.pc!=boundary;n++)pc1715_run(&m,1);
  assert(n<2000000);
  const char *banner="CP/M Plus 3.1 - Robotron 1715\r\nA>";
  for(const char *p=banner;*p;p++){m.cpu.cpu.c=*p;call(localout);}
  assert(!memcmp(m.ram+0xf800,banner,27));
  assert(m.ram[0xf850]=='A' && m.ram[0xf851]=='>');
  pc1715_run(&m,PC1715_CLOCK_HZ/20);
  unsigned lit=0;for(n=0;n<640*288;n++)lit+=m.video.pixels[n]!=0xff000000;
  if(legacy){assert(!m.video.running && !m.video.fetches && !lit);}
  else {
    check_raster();assert(lit);
    /* Character wrapping, CR/LF, backspace, tabs and scroll across row 24. */
    for(unsigned i=0;i<30;i++) {
      const char *line="\r\nROW\tABCDEFG\bZ";
      for(const char *p=line;*p;p++){m.cpu.cpu.c=*p;call(localout);}
    }
    check_raster();assert(m.video.reg[5]==23);
    m.cpu.cpu.c=12;call(localout);check_raster();
    assert(m.video.reg[4]==0 && m.video.reg[5]==0);
    for(n=0;n<1920;n++)assert(m.ram[0xf800+n]==32);
    for(const char *p=banner;*p;p++){m.cpu.cpu.c=*p;call(localout);}
    check_raster();
  }
  f=fopen(argv[6],"wb");assert(f);fprintf(f,"P6\n640 288\n255\n");
  for(n=0;n<640*288;n++){unsigned char rgb[3]={m.video.pixels[n]>>16,m.video.pixels[n]>>8,m.video.pixels[n]};fwrite(rgb,1,3,f);}fclose(f);
  printf("{\"legacy\":%u,\"screen_ram_has_banner\":true,\"running\":%u,\"lit_pixels\":%u,\"fetches\":%llu,\"underruns\":%llu}\n",legacy,m.video.running,lit,(unsigned long long)m.video.fetches,(unsigned long long)m.video.underruns);
}
