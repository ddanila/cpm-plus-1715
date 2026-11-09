#!/usr/bin/env python3
"""Linux exec wrapper: terminate the native host if its supervisor disappears."""
import ctypes
import os
import signal
import sys


def main():
    parent = int(sys.argv[1])
    libc = ctypes.CDLL(None, use_errno=True)
    # Linux PR_SET_PDEATHSIG, inherited across exec of the ordinary host binary.
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'PR_SET_PDEATHSIG')
    if os.getppid() != parent:
        return 1
    os.execv(sys.argv[2], sys.argv[2:])


if __name__ == '__main__':
    raise SystemExit(main())
