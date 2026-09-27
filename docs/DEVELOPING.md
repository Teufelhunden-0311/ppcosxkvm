# Developing

## Layout

```
ppcosx                  the launcher: setup, install, import, run, …
install.sh              the one-line installer (clone to ~/.ppcosx, setup, link)
firmware/               OpenBIOS, ndrvloader, NDRV (+ sources/patchers in src/)
  radeon/               firmware for the Radeon mode
  vga/                  stock UTM firmware for installing and --vga
  SHA1SUMS              checked by ppcosx doctor
qemu/                   git submodule: the QEMU fork (branch r300)
  hw/display/ppc_mac_gpu.c        the device: PCI, MMIO, CP/PM4, GART, 2D, scanout
  hw/display/ppc_mac_gpu_metal.m  Metal backend
  hw/display/r300/                R300 3D: state, PVS, US→MSL, draw assembly
  tests/r300/                     offline tests (run.sh)
tools/vmctl.py          drive a running VM: keys, clicks, screenshots, HMP
docs/                   these documents
vm/                     your disks, ROM and logs (git-ignored)
```

## Rebuilding

After changing QEMU sources:

```bash
ninja -C qemu/build qemu-system-ppc
ppcosx run
```

`ppcosx setup` does the same, and also re-runs configure on a fresh
build directory.

## Updating the QEMU fork

`qemu/` is a submodule tracking the `r300` branch of the fork:

```bash
cd qemu
git fetch origin r300 && git checkout -B r300 FETCH_HEAD   # once
<commit your changes> && git push origin r300
cd .. && git add qemu && git commit -m "qemu: bump"      # pin the new commit
```

The fetch is needed because `setup` clones `qemu/` shallow at the pinned
commit, which only tracks the fork's default branch (`poweremu`), not
`r300`.

Users get it with `git pull && git submodule update --init --depth 1 && ppcosx setup`.

## Offline tests

The R300 translation layers are tested without a guest:

```bash
qemu/tests/r300/run.sh
```

This runs the vertex-program interpreter, fragment-program → MSL
translation (compiled by the Metal compiler to check the output is valid),
draw assembly, depth/stencil, formats and rasterizer tests. A few of them
render through Metal.

## Debug switches

Environment variables read by the device. Set them in front of `ppcosx run`:

| Variable | Effect |
|---|---|
| `R300_DRAWLOG=path` | One line per draw: state summary, shaders, targets. The fastest way to find which draw is wrong. |
| `R300_DUMP=path` | Full per-draw state plus register trace, and dumps of textures and render targets (`path.NN.*.bin`). |
| `R300_RINGDUMP=path` | Raw command-ring contents. |
| `R300_SURFWATCH=1` | Log CPU accesses to the VRAM range the driver maps through a `SURFACE` register (e.g. depth readback for picking). |
| `R300_SYNC=1` | Flush to Metal after every draw instead of batching (isolates ordering bugs). |
| `PPCGPU_SEQ_LOG=1` | Packet sequence log (`/tmp/gpu_seq.log`), including 2D blits (`BBMRAW`) and 3D (`R3D`) lines. |
| `PPCGPU_DEBUG_LOG=1` | General device debug log. |
| `QEMU_COCOA_SRGB=1` | Exact sRGB colour conversion in the Cocoa UI (slower). |
| `QEMU_PPC_NDRV=path` | Use a different NDRV (set by `ppcosx run`). |

`ppcosx run --trace-gpu` enables QEMU's `ppc_mac_gpu_*` trace events (every
register access) into `vm/gpu-trace.log`. It's large and slow, but complete.

Example:

```bash
R300_DRAWLOG=/tmp/draws.log ppcosx run --snapshot --verbose
```

## Driving the guest from scripts

`ppcosx run --monitor` opens the QEMU monitor on 127.0.0.1:4444 (HMP) and
4445 (QMP). `tools/vmctl.py` wraps it:

```bash
tools/vmctl.py shot /tmp/screen.png
tools/vmctl.py key meta_l-spc          # Cmd+Space: Spotlight
tools/vmctl.py type 'Terminal'
tools/vmctl.py key ret
tools/vmctl.py click 512 384
tools/vmctl.py cmd 'info pci'
```

Useful HMP commands: `xp /2wx 0xa000ff0c` reads the hardware cursor
position (the MMIO BAR is at 0xA0000000), and `info registers` samples the
guest CPU (useful for finding where the ATI kext is spinning).

## Reading the ATI kext

`ATIRadeon9700.kext` is an `MH_OBJECT` with symbols, which makes it very
readable. Homebrew's LLVM disassembles PowerPC Mach-O:

```bash
brew install llvm
$(brew --prefix llvm)/bin/llvm-objdump --macho -d ATIRadeon9700 | less
```

The kext's load address changes on every boot. Find it from `info
registers` LR samples while the guest is inside the driver.

To pull files out of a guest disk on the host (modern macOS can no longer
mount HFS+): `qemu-img convert -O raw` the disk, cut out the HFS partition
(from the Apple partition map offset), then `7zz x` it (`brew install sevenzip`).

## Lessons worth knowing

These each cost real time. See `git log` in `qemu/` for the details.

* The R300 GART table base is register **0x0AB0**, not the R200's
  `AIC_PT_BASE` (0x1D8).
* PM4 type-3 opcode **0x1B** is a header-less `BITBLT_MULTI` continuation.
  It reuses the previous 0x9B's control word. Window dragging depends on it.
* Type-3 **0x38** is `3D_CLEAR_CMASK` (fast colour clear). Dropping it
  leaves trails.
* Tiger's desktop sets `US_OUT_FMT` to C4_10 on an ARGB8888 buffer. The
  *buffer* format decides storage, not the output format.
* Register **0x15D4** is the source endian swap for GART→VRAM uploads.
* Frame drops that look like GPU slowness were host-side Core Animation
  colour conversion. Profile with `sample <qemu pid> 8` before guessing.
