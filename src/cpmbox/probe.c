/* Qualification-only RSX/TPA probe; not installed on release images. */
#include <stdio.h>
#include <cpm.h>
extern char _piped;
int main(int argc, char **argv)
{
    int c, i, n = 1;
    for(i=1; i<argc; ++i) if(argv[i][0]) argv[n++]=argv[i];
    if (!_piped) { puts("NO RSX"); return 1; }
    if(n > 1) while((c=getchar()) != EOF) putchar(c);
    else puts("RSX PROBE OK");
    return 0;
}
