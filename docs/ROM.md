# The ATI Radeon 9700 PRO ROM

**You don't need one.** Tiger's desktop, Quartz Extreme, Core Image, OpenGL
and System Profiler's "ATI Radeon 9700 Pro" entry all work without a ROM.

## Why it's optional

On a real Mac, the card's ROM holds Open Firmware FCode that builds the
card's device-tree node and publishes its identity (`ATY,…` properties),
plus an NDRV (the Mac OS display driver). Here those jobs are done
differently:

* the patched OpenBIOS in `firmware/radeon/` builds the display node,
* `ppcosx run` adds the 9700 PRO identity properties (`model = ATY,R300`,
  `ATY,Rom#`, …) from its Open Firmware boot command, and
* the QEMU VGA NDRV in `firmware/radeon/` drives the framebuffer.

Tiger's `ATIRadeon9700.kext` programs the chip directly and doesn't read
the ROM for anything the emulation needs.

## Using one anyway

If you have the ROM of a real **Mac** Radeon 9700 PRO (for example, dumped
from your own card), the emulated card will expose it as its PCI expansion
ROM and copy it to the start of VRAM, where a real card's POST would shadow
it:

```bash
./ppcosx rom ~/radeon9700pro-mac.rom
./ppcosx run                      # uses it automatically
./ppcosx run --no-rom             # skip it for one boot
./ppcosx rom --remove             # stop using it
```

`ppcosx rom` checks the file first. It must:

* start with the PCI ROM signature `55 AA`,
* be for **1002:4E44** (Radeon 9700 PRO, "ATY,GoldenEye"), and
* be a **Mac (Open Firmware) image**, code type 1. PC ROMs (x86 BIOS) are
  rejected.

The tested ROM is the Mac 9700 PRO `113-A06500-124` (FCode 1.88, SHA-1
`8be6cbf365b112cd5585e24cae56a1abb79ee041`).

The ROM is ATI/AMD copyrighted and isn't distributed with this project.
Please don't open issues asking for it.
