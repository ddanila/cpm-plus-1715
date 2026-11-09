/* Shared Robotron/HI-TECH adaptation for cpmbox (GPL-3.0-or-later). */
#ifndef BOX_PORT_H
#define BOX_PORT_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <cpm.h>
#include <unixio.h>
#include "errno.h"
extern char _piped;
extern int pm_redirected(void);
extern void pm_exit(int);
extern void pm_fail(char *);
extern FILE *pm_error_stream(void);
#define exit pm_exit
#endif
