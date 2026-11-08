/* MIT. Real-time byte-level SIO-B harness; no host BDOS or RAM injection. */
#define _POSIX_C_SOURCE 200809L
#include "machines/robotron1715/pc1715.h"
#include "model/controller.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
static volatile sig_atomic_t stop;
static void stopped(int sig){(void)sig;stop=1;}
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;}
/* ROM probes four units before V.24. Model four equally unreadable scratch
 * drives by routing their select lines to the same read-only field model. */
static void boot_card_write(void *p,uint16_t address,uint8_t data){
 if((address&0xfc)==0x20)data&=(uint8_t)~0x10u;
 pico1715_write(p,address,data);
}
static void trace_serial(void *p,const dac_trace_event *e){
 (void)p;
 if(e->kind[0]=='I' && e->kind[1]=='W' && ((e->address&255)==15 || (e->address&255)==13) && e->data)
 fprintf(stderr,"SIO write %02x = %02x\n",e->address&255,e->data);
}
typedef struct {int fd;unsigned prefix,remaining,armed,corrupt_after,injected;} link_state;
static void tx(void *p,uint8_t b){
 link_state *link=p;
 if(write(link->fd,&b,1)!=1)stop=1;
 if(link->remaining){link->remaining--;return;}
 if(link->prefix==0){if(b=='J')link->prefix=1;}
 else if(link->prefix==1){link->prefix=b=='D'?2:b=='J'?1:0;}
 else {
  if(link->armed && (b==0x14 || b==0x15)){link->corrupt_after=3;link->armed=0;}
  link->remaining=b==0x15?134:6;link->prefix=0;
 }
}
int main(int argc,char **argv){
 if(argc!=4 && argc!=5)return 2;
 int control=argc==5?atoi(argv[4]):-1;int key_pending=0;
 if(control>=0)fcntl(control,F_SETFL,fcntl(control,F_GETFL)|O_NONBLOCK);
 int fd=atoi(argv[2]);pc1715 *m=calloc(1,sizeof(*m));if(!m)return 2;
 pc1715_init(m);
 /* An unreadable scratch floppy supplies the ROM's index/PIO environment.
  * It never supplies CP/M: all system records arrive over SIO B. */
 pico1715_controller controller={0};uint8_t *scratch=calloc(819200,1);
 if(!scratch || pico1715_mount(&controller,scratch,819200,80,2,5,3))return 2;
 controller.timing.corrupt_crc=1;
 pc1715_card card={.user=&controller,.read=pico1715_read,.write=boot_card_write,
  .tick=pico1715_tick,.irq=pico1715_irq,.ack=pico1715_ack,.reti=pico1715_reti,.reset=pico1715_reset};
 pc1715_attach(m,&card);
 FILE *f=fopen(argv[1],"rb");uint8_t rom[2048];
 if(!f||fread(rom,1,sizeof rom,f)!=sizeof rom||fgetc(f)!=EOF)return 2;
 fclose(f);pc1715_load(m,rom,sizeof rom);pc1715_onboard_enable(m);
 unsigned ticks=(PC1715_CLOCK_HZ*12u+9599u)/9600u;
 link_state link={.fd=fd};pc1715_sio_link(m,1,ticks,&link,tx);
 if(getenv("P1715_SERIAL_TRACE"))m->trace=(dac_trace_sink){trace_serial,NULL,0,0};
 fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)|O_NONBLOCK);
 signal(SIGTERM,stopped);signal(SIGINT,stopped);
 uint64_t start=ns(),base=0,next_rx=0, report=0;int realtime=0;unsigned dropped=0;unsigned badpc=getenv("P1715_BAD_PC")?strtoul(getenv("P1715_BAD_PC"),NULL,16):0;unsigned lastpc=0;
 while(!stop){
  if(control>=0){uint8_t command;if(read(control,&command,1)==1){
    if(key_pending){(void)pc1715_sio_receive(m,0,command);key_pending=0;}
    else if(command=='K')key_pending=1;
    else if(command=='F')link.armed=1;
    else if(command=='R'){link.prefix=link.remaining=link.armed=link.corrupt_after=0;pc1715_reset(m);realtime=0;start=ns();base=next_rx=report=0;}
  }}
  if(m->cpu.cycles>=report){fprintf(stderr,"pc=%04x cycles=%llu\n",m->cpu.cpu.pc,(unsigned long long)m->cpu.cycles);fprintf(stderr," sel=%02x irq=%u svc=%u idx=%llu ram800=%u\n",controller.select,controller.irq_enabled,controller.service,(unsigned long long)controller.interrupts,m->ram[0x800]);fflush(stderr);report=m->cpu.cycles+PC1715_CLOCK_HZ*5u;}
  if(!realtime && ((m->cpu.cpu.pc>=0x5d7 && m->cpu.cpu.pc<0x677) || m->sio[1].wr[3]==0xc1)){realtime=1;start=ns();base=m->cpu.cycles;}
  uint64_t target=realtime?base+(ns()-start)*PC1715_CLOCK_HZ/1000000000u:m->cpu.cycles+24580;
  if(target>m->cpu.cycles+24580)target=m->cpu.cycles+24580;
  while(m->cpu.cycles<target){
   if(m->cpu.cycles>=next_rx){uint8_t b;ssize_t n=read(fd,&b,1);
    if(n==1){if(link.corrupt_after && !--link.corrupt_after){b^=1;link.injected++;}
    int accepted=pc1715_sio_receive(m,1,b);if(accepted!=0)dropped++;next_rx=m->cpu.cycles+ticks;}
    else if(n<0 && errno!=EAGAIN && errno!=EINTR && errno!=EIO)stop=1;
   }
   if(badpc && m->cpu.cpu.pc==badpc && lastpc!=badpc)fprintf(stderr,"BAD af=%04x bc=%04x de=%04x hl=%04x fifo=%u\n",m->cpu.cpu.af,m->cpu.cpu.bc,m->cpu.cpu.de,m->cpu.cpu.hl,m->sio[1].count);
   lastpc=m->cpu.cpu.pc;pc1715_run(m,1);
  }
  if(realtime){struct timespec delay={0,100000};nanosleep(&delay,NULL);}
 }
 f=fopen(argv[3],"wb");if(f){fwrite(m->ram,1,65536,f);fclose(f);}
 fprintf(stderr,"injected=%u\n",link.injected);
 fprintf(stderr,"cycles=%llu dropped=%u pc=%04x sioB=%02x/%02x/%02x ctcB=%02x/%u\n",(unsigned long long)m->cpu.cycles,dropped,m->cpu.cpu.pc,m->sio[1].wr[3],m->sio[1].wr[4],m->sio[1].wr[5],m->ctc[1].control,m->ctc[1].reload);
 free(scratch);free(m);return 0;
}
