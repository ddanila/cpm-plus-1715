/* HI-TECH's CP/M errno values; private cpmbox-only errors use 100+. */
#ifndef BOX_ERRNO_H
#define BOX_ERRNO_H
extern int errno;
#define ENOENT 7
#define ENOMEM 100
#define EMFILE 101
#define ENFILE 102
#define EEXIST 8
#define EACCES 3
#define ENOTTY 103
#define EBADF 104
#define E2BIG 105
#define EDOM 106
#define ERANGE 107
#define EINVAL 108
#endif
