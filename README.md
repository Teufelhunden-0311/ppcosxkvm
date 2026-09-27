# ppcosxkvm

**PowerPC Mac OS X Tiger on Apple Silicon, with real 3D.** A patched QEMU
emulates a Power Mac G4 with an **ATI Radeon 9700 PRO**. Tiger's own ATI
driver runs the emulated card, and the card's 3D engine is translated to
Metal on the host GPU. Quartz Extreme, Core Image and OpenGL work on the
emulated card.

```
┌ Mac OS X 10.4 (PowerPC) ───────────────────────────┐
│  WindowServer / OpenGL apps                        │
│  ATIRadeon9700.kext + ATI GL driver (Apple's own)  │
└──────────── R300 registers, command ring ──────────┘
┌ QEMU (this repo's fork) ───────────────────────────┐
│  ati-radeon-9700: CP/PM4, GART, R300 3D state      │
│  vertex programs → CPU, fragment programs → MSL    │
└──────────────────── Metal ─────────────────────────┘
        Apple Silicon GPU
```

System Profiler in the guest reports an **ATI Radeon 9700 Pro** (`ATY,R300`),
with Quartz Extreme and Core Image both *Supported*.

## Quick start

You need an Apple Silicon Mac, [Homebrew](https://brew.sh), and **your own**
Mac OS X Tiger (PowerPC) install DVD image or an already installed PowerPC
OS X disk.

```bash
git clone --recursive https://github.com/linuxkid473/ppcosxkvm.git
cd ppcosxkvm
./ppcosx setup
```

`setup` installs a few Homebrew packages and builds QEMU (about 5–10
minutes, once). Then either install Tiger from a DVD image:

```bash
./ppcosx install ~/Downloads/MacOSX-10.4-Tiger.iso
```

or bring a disk you already have (`.vmdk`, `.qcow2`, `.vdi`, `.vhd`, raw
`.img`, or a whole UTM `.utm` bundle):

```bash
./ppcosx import ~/VMs/Tiger.vmdk
```

and boot it:

```bash
./ppcosx run
```

`./ppcosx doctor` checks everything, and `./ppcosx help` lists all commands.

## Documentation

| | |
|---|---|
| [Getting started](docs/GETTING-STARTED.md) | Setup, installing Tiger step by step, importing a disk, first boot |
| [Using ppcosx](docs/USAGE.md) | Every command and option, keyboard and mouse, snapshots, networking |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Things that go wrong, and fixes |
| [The ATI ROM](docs/ROM.md) | Why the ROM is optional, and how to use one |
| [How it works](docs/HOW-IT-WORKS.md) | The emulated Radeon, the boot chain, the Metal translation |
| [Developing](docs/DEVELOPING.md) | Repo layout, rebuilding, debug switches, tests |

## Status

Verified on Tiger 10.4.11:

| Works | Notes |
|---|---|
| Desktop with Quartz Extreme | Window server compositing, window dragging, the Dock, QuickTime movies |
| Core Image | Reported as *Supported*; the R300 fragment programs it needs are implemented |
| OpenGL apps | Chess is the main test: depth, stencil, 2× MSAA, textures, picking |
| Hardware cursor, USB keyboard and mouse | |
| System Profiler shows "ATI Radeon 9700 Pro" | Works without an ATI ROM |

Expected to work but not re-tested since the move to `ppcosx`: networking
(NAT), sound, and **installing from a DVD image** (`ppcosx install` uses the
standard QEMU Tiger recipe; please open an issue if it fails for you).

**Not yet:** Leopard (untested), more than 1024×768 in the Radeon mode
(experimental; use `--res`), and multiple CPUs (the guest is a single G4 on
TCG, so expect a fast G4 rather than a G5). See the
[limitations](docs/HOW-IT-WORKS.md#limitations).

## Legal

* The launcher, docs and tools in this repo are GPL-2.0-or-later
  ([LICENSE](LICENSE)). The QEMU fork (`qemu/`) is GPL-2.0, like QEMU.
* The firmware in [`firmware/`](firmware/README.md) is free software (OpenBIOS
  GPL-2.0, QemuMacDrivers GPL-2.0, ndrvloader MIT).
* **No Apple or ATI software is included.** You supply Mac OS X yourself, and
  the ATI ROM is optional.

## Credits

Built on [QEMU](https://www.qemu.org),
[Spartan0285/poweremu-qemu](https://github.com/Spartan0285/poweremu-qemu)
(the RV280 / Radeon 9200 emulation this extends to the R300), and
[PowerEmu](https://github.com/Spartan0285/PowerEmu) (the hardware cursor NDRV
patcher). It also uses [OpenBIOS](https://github.com/openbios/openbios) as
shipped by [UTM](https://github.com/utmapp/UTM),
[QemuMacDrivers](https://github.com/ozbenh/QemuMacDrivers),
[classicvirtio](https://github.com/elliotnunn/classicvirtio), and Mesa's
r300 documentation.
