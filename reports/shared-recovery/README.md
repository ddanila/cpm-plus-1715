# Shared recovery emulator evidence

These reports exercise production launchers and actual emulated ROM/CP/M code.
They are software qualification, not physical-link qualification. Session files
survive host restart and modeled power cycles. No new ROM burn is required.

Kaypro reset trials distinguish bytes lost while power-cycling a receiver from
runtime overruns; successful bootstrap CRC and zero runtime drops are required.
Earlier exploratory failures were retained locally: an unsolicited ready marker
caused an overrun (fixed by waiting for a checked guest request); the host screen
needed clearing on confirmed reboot; changing source files mid-test correctly
failed the helper integrity check. Final passing reports are included here.

Integration source revision (the per-report executable hashes identify the exact test builds): c8ecee158538e5bda0b5852bf9bd6eee20f82c68
