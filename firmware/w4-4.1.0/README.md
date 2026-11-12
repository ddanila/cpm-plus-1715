# W4 firmware 4.1.0 candidate

Burn `rom-w4.bin` as a complete 2048-byte 2716 image. This is for the PC1715W/M
board (PC001), not the plain PC1715. Verify SHA256SUMS before programming.

This is a copy of RAVI's canonical ROM, pinned by tools/wm-dependencies.json.
Protocol remains W4. A locked monitor now returns to baud scanning after 16
idle intervals (about 9.5 seconds); an active command stream refreshes that
budget. A fresh handshake is required after expiry. This lets a replacement
host recover at another supported speed without resetting the board.

The font, readable status, version query, build identity, whole-ROM CRC and
62400/41600/9600 scan remain. Used: 1908 bytes; padding: 138 bytes; CRC: 2 bytes.
No stack or main-RAM workspace is added.

Actual-ROM emulator tests exercise idle expiry, all supported speeds, headless
and no-RAM operation, corrupt transfers, transmit stalls and diagnostic return.
Banked CP/M at 62400 passed boot, verified writes, host restart and two modeled
power cycles (see cpm-auto-result.json). Physical 4.1.0 qualification is pending;
the previous 4.0.0 image remains the hardware-tested fallback in git history.
