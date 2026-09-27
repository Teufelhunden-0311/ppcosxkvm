# Firmware

Everything in this folder is free software and may be redistributed. Nothing
here comes from Apple or ATI. `SHA1SUMS` lists the expected checksums, and
`./ppcosx doctor` verifies them.

| File | What it is | Origin | License |
|---|---|---|---|
| `vga/openbios-ppc` | OpenBIOS 1.1, the PowerPC Mac firmware. Used by `ppcosx install` and `ppcosx run --vga`. | Copied unmodified from UTM 4.7.5 (`UTM.app/Contents/Resources/qemu/openbios-ppc`). The OpenBIOS in `qemu/pc-bios` hangs before the display comes up on this machine setup. | GPL-2.0. Source: [openbios/openbios](https://github.com/openbios/openbios), as built by [UTM](https://github.com/utmapp/UTM) |
| `radeon/openbios-ppc` | The same OpenBIOS, with its built-in VGA table entry changed from QEMU VGA (1234:1111) to the Radeon 9700 PRO (1002:4E44). | `src/patch-openbios.py vga/openbios-ppc radeon/openbios-ppc` (a 4-byte change at 0x30678) | GPL-2.0 |
| `*/ppc-ndrvloader` | Boot helper loaded at 0x4000000 and started by `init-program go`. | UTM 4.7.5; identical to `qemu/pc-bios/ppc-ndrvloader` | MIT. Source: [elliotnunn/classicvirtio](https://github.com/elliotnunn/classicvirtio) |
| `radeon/qemu_vga_hwc.ndrv` | The QEMU VGA NDRV (the Mac OS display driver that runs the framebuffer before and alongside the ATI kext), patched for a hardware cursor and extra modes. | `python3 src/ndrv/build.py src/ndrv/qemu_vga.orig.ndrv radeon/qemu_vga_hwc.ndrv` gives a byte-identical file. | GPL-2.0. Base: [ozbenh/QemuMacDrivers](https://github.com/ozbenh/QemuMacDrivers). Patcher: [Spartan0285/PowerEmu](https://github.com/Spartan0285/PowerEmu) `ndrv/` |

## What is *not* here, and why

* **The ATI Radeon 9700 PRO ROM** is ATI/AMD copyrighted, so it can't be
  shipped. It's optional; see [docs/ROM.md](../docs/ROM.md).
* **Mac OS X** and its drivers (`ATIRadeon9700.kext` and the OpenGL bundles)
  come from your own install disc.
