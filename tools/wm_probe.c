/* MIT. Actual W/M CPU/device execution through a PTY, no RAM/PC injection.
 * Video board, keyboard and floppy media are absent. */
#define _POSIX_C_SOURCE 200809L
#include "machines/robotron1715m/robotron.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
static volatile sig_atomic_t stop;
static void stopped(int s) {
  (void)s;
  stop = 1;
}
static uint64_t ns(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (uint64_t)t.tv_sec * 1000000000u + t.tv_nsec;
}
static uint8_t rd(void *p, uint16_t a) {
  unsigned map = robotron_mapping(p, a, 0) >> 24;
  if (map == DAC_SPACE_VIDEO || map == DAC_SPACE_GLYPHS)
    return 255;
  return robotron_read(p, a);
}
static void wr(void *p, uint16_t a, uint8_t v) {
  unsigned map = robotron_mapping(p, a, 1) >> 24;
  if (map != DAC_SPACE_VIDEO && map != DAC_SPACE_GLYPHS)
    robotron_write(p, a, v);
}
static uint8_t inp(void *p, uint16_t a) {
  if ((a & 255) == 0x18 || (a & 255) == 0x19)
    return 255;
  uint8_t v = robotron_input(p, a);
  robotron *m = p;
  static unsigned count;
  if (getenv("WM_TRACE") && m->cpu.cpu.pc >= 0xc000 && (a & 255) == 13 &&
      count++ < 1500)
    fprintf(stderr, "RX %02x pc=%04x\n", v, m->cpu.cpu.pc);
  return v;
}
static void outp(void *p, uint16_t a, uint8_t v) {
  static unsigned count;
  robotron *m = p;
  if (getenv("WM_TRACE") && m->cpu.cpu.pc >= 0xc000 && (a & 255) == 13 &&
      count++ < 1000)
    fprintf(stderr, "TX %02x pc=%04x\n", v, m->cpu.cpu.pc);
  if ((a & 255) != 0x18 && (a & 255) != 0x19)
    robotron_output(p, a, v);
}
int main(int argc, char **argv) {
  if (argc != 4 && argc != 5)
    return 2;
  robotron *m = calloc(1, sizeof(*m));
  if (!m)
    return 2;
  robotron_init(m);
  FILE *f = fopen(argv[1], "rb");
  if (!f || fread(m->rom, 1, 2048, f) != 2048 || fgetc(f) != EOF)
    return 2;
  fclose(f);
  /* Synthetic equivalent CAS fixture, not a specimen PROM dump. */
  for (unsigned i = 0; i < 256; i++)
    m->prom[i] = 15;
  for (unsigned b = 1; b <= 4; b++)
    for (unsigned pg = 0; pg < 16; pg++)
      m->prom[128 + b * 16 + pg] = (pg >= 12 ? 1 : 1u << (b - 1)) ^ 15;
  m->cpu.bus.read = rd;
  m->cpu.bus.write = wr;
  m->cpu.bus.input = inp;
  m->cpu.bus.output = outp;
  m->disconnected = 3;
  m->v24.peer_baud = 1200;
  m->v24.peer_format = 0x208;
  m->v24.signals = 3;
  int fd = atoi(argv[2]);
  fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
  signal(SIGTERM, stopped);
  signal(SIGINT, stopped);
  uint64_t start = ns(), report = 0;
  unsigned speed = getenv("WM_SPEED") ? (unsigned)atoi(getenv("WM_SPEED")) : 8;
  if (!speed || speed > 32)
    return 2;
  unsigned fixed_baud = argc == 5 ? (unsigned)atoi(argv[4]) : 0;
  if (fixed_baud && fixed_baud != 9600 && fixed_baud != 41600 && fixed_baud != 62400) return 2;
  while (!stop) {
    struct termios a;
    if (fixed_baud) m->v24.peer_baud = fixed_baud;
    else if (tcgetattr(fd, &a) == 0)
      m->v24.peer_baud = cfgetospeed(&a) == B9600 ? 9600 : 1200;
    uint8_t buf[4096];
    ssize_t n = read(fd, buf, sizeof buf);
    if (n > 0) {
      for (ssize_t i = 0; i < n; i++) {
        if (m->v24.count == 65536) {
          stop = 1;
          break;
        }
        m->v24.input[(m->v24.read + m->v24.count++) % 65536] = buf[i];
      }
    } else if (n < 0 && errno != EAGAIN && errno != EINTR && errno != EIO)
      stop = 1;
    uint64_t elapsed = ns() - start;
    uint64_t target = (elapsed / 1000000000u) * 3993600u * speed +
                      (elapsed % 1000000000u) * 3993600u * speed / 1000000000u;
    if (target > m->cpu.cycles + 16000)
      target = m->cpu.cycles + 16000;
    if (target > m->cpu.cycles)
      robotron_run(m, (unsigned)(target - m->cpu.cycles));
    if (m->v24.decoded_size) {
      ssize_t sent = write(fd, m->v24.decoded, m->v24.decoded_size);
      if (sent > 0) {
        unsigned left = m->v24.decoded_size - (unsigned)sent;
        for (unsigned i = 0; i < left; i++)
          m->v24.decoded[i] = m->v24.decoded[i + sent];
        m->v24.decoded_size = left;
      }
    }
    m->v24.size = 0;
    if (m->cpu.pins & Z80_HALT) {
      fprintf(stderr, "CPU HALT pc=%04x\n", m->cpu.cpu.pc);
      stop = 1;
    }
    if (m->cpu.cycles >= report) {
      fprintf(stderr, "pc=%04x bank=%02x wr4=%02x peer=%u rx_errors=%02x\n",
              m->cpu.cpu.pc, m->bank, m->sio_regs[1][4], m->v24.peer_baud,
              m->rx_b.errors);
      report = m->cpu.cycles + 3993600u * 10;
    }
    struct timespec delay = {0, 100000};
    nanosleep(&delay, 0);
  }
  f = fopen(argv[3], "wb");
  if (f) {
    fwrite(m->ram, 1, sizeof m->ram, f);
    fclose(f);
  }
  free(m);
  return 0;
}
