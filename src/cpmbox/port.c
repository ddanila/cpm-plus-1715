/* Shared Robotron/HI-TECH adaptation for cpmbox (GPL-3.0-or-later). */
#include "port.h"
#undef exit
#include <signal.h>
static void interrupted(int sig) { pm_exit(1); }
static int failed, exiting;
static char pmname[] = "PIPEMGR ";
struct rsxpb { unsigned char fn, count; char *name; };
int pm_redirected(void)
{
    struct rsxpb pb;
    if (!_piped) return 0;
    pb.fn = 0x76; pb.count = 1; pb.name = pmname;
    return (bdos(60, &pb) >> 8) & 31;
}
FILE *pm_error_stream(void) { failed = 1; return stderr; }
void pm_exit(int status)
{
    struct rsxpb pb;
    exiting = 1;
    signal(SIGINT, SIG_IGN);
    if (fflush(stdout) || ferror(stdout) || ferror(stdin)) failed = 1;
    fflush(stderr);
    if (status || failed) {
        if (_piped) {
            pb.fn = 0x7e; pb.count = 1; pb.name = pmname;
            bdos(60, &pb);
            setuid(0);
            unlink("A:PIPEIN.$$$");
            unlink("A:PIPEOUT.$$$");
        }
        bdos(108, 0xff);
    }
    exit(status || failed);
}
void pm_fail(char *s) { fputs(s, stderr); fputs("\n", stderr); pm_exit(1); }
int main(int argc, char **argv)
{
    int i, n = 1;
    extern int box_main(int, char **);
    for (i = 1; i < argc; ++i) if (argv[i][0]) argv[n++] = argv[i];
    argv[n] = 0;
    for (i = 1; i < n; ++i) {
        if (strlen(argv[i]) > 14) pm_fail("Argument too long");
        if (strchr(argv[i], ':') && (argv[i][1] != ':' || argv[i][0] != 'A'))
            pm_fail("Only A: is available");
    }
    signal(SIGINT, (signal_t)interrupted);
    bdos(45, 0xfe); /* Return disk errors to callers; no interactive BDOS prompt. */
    pm_exit(box_main(n, argv));
    return 0;
}

