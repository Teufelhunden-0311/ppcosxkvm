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
  hw/display/ppc_mac_gpu_vulkan.c Vulkan backend (MoltenVK on macOS)
  hw/display/r300/                R300 3D: state, PVS, US→GLSL, SPIR-V/MSL, draw assembly
  target/ppc/translate/vmx-impl.c.inc  AltiVec translation (inline NEON shuffles)
  target/ppc/int_helper.c         AltiVec helpers (host-FPU fast paths)
  tcg/                            TCG, with the tbl_vec vector op (AArch64 backend)
  tests/r300/                     offline R300 tests (run.sh)
  tests/ppc-vmx/                  bare-metal AltiVec correctness + speed test (run.py)
tools/vmctl.py          drive a running VM: keys, clicks, screenshots, HMP
tools/build-linux-qemu.sh  build the prebuilt Linux QEMU tarball
.github/workflows/      CI: builds that tarball for each pinned qemu/ commit
docs/                   these documents
vm/                     your disks, ROM and logs (git-ignored)
prebuilt/               Linux only: the downloaded prebuilt QEMU (git-ignored)
```

Inherited from the PowerEmu fork and not used by `ppcosx`: the R200
device model (`ppc-mac-gpu` without `r300`, the Radeon 9200 path, still
built and sharing most of `ppc_mac_gpu.c`), `hw/display/poweremu-gpu.c` (a
paravirtual GPU for a cooperating guest driver) and the "harmony"
window tracking (`ui/poweremu-display.c`, `PPCGPU_WINDOWS`).

## Rebuilding

After changing QEMU sources:

```bash
ninja -C qemu/build qemu-system-ppc
ppcosx run
```

`ppcosx setup` does the same, and also re-runs configure on a fresh
build directory.

On macOS, `setup` gets the libraries from Homebrew on Apple Silicon and
from MacPorts on Intel Macs (`PPCOSX_PKG=brew|macports` overrides it). The
lists are `BREW_DEPS` and `PORT_DEPS` at the top of `ppcosx`. QEMU finds
them all through `pkg-config`, so nothing else in the build knows which
one it was.

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

`origin` here is the URL in `.gitmodules`
(`linuxkid473/poweremu-qemu`). If your checkout's `origin` is the
upstream `Spartan0285/poweremu-qemu` instead, add the fork as another
remote and push there; pushing upstream is refused.

Users get it with `git pull && git submodule update --init --depth 1 && ppcosx setup`.

Pushing a new pin to `main` also starts the **Linux QEMU** workflow
(`.github/workflows/qemu-linux.yml`). It runs `tools/build-linux-qemu.sh`
on Ubuntu 24.04 (x86_64 and arm64) and attaches
`ppcosx-qemu-linux-<arch>.tar.xz` to a release named `qemu-<first 12
characters of the qemu commit>`. On Linux, `ppcosx setup` downloads the
tarball matching the pinned commit into `prebuilt/`, checks that it runs
(`ldd`, `--version`), and builds from source if there isn't one yet or
it doesn't run. `ppcosx setup --build` always builds.

## Offline tests

The R300 translation layers are tested without a guest:

```bash
qemu/tests/r300/run.sh
```

This runs the vertex-program interpreter, fragment-program → GLSL
translation (both variants: validated as SPIR-V with `glslangValidator`
and `spirv-val`, and cross-compiled to MSL and checked by the Metal
compiler), draw assembly, depth/stencil, formats and rasterizer tests,
and `test_gpuvs`, which checks that vertex programs give the same
results on the GPU as in the interpreter. A few of them render through
Metal. It needs `brew install shaderc spirv-cross glslang` (`ppcosx
setup` installs them).

The AltiVec translation is tested in a guest with no OS at all:

```bash
qemu/tests/ppc-vmx/run.py [path/to/qemu-system-ppc]
```

It builds `vmx_test.c` with Homebrew's clang (`brew install llvm lld`)
into a raw mac99 firmware image and boots it. The image runs every op
converted to NEON or the host FPU on random and edge-case inputs,
compares each against a scalar reference (including `VSCR[SAT]`), and
times a few chains of them. It prints any mismatch with its inputs, the
timings, and `188000 checks, 0 failures`. To compare timings against
QEMU's helpers, make `vmx_host_tbl()` in `vmx-impl.c.inc` return false
and rebuild.

## Debug switches

Environment variables read by QEMU. Set them in front of `ppcosx run`,
e.g. `R300_DRAWLOG=/tmp/draws.log ppcosx run --snapshot --verbose`.

**R300 3D (the Radeon 9700):**

| Variable | Effect |
|---|---|
| `R300_DRAWLOG=path` | One line per draw: state summary, shaders, targets. The fastest way to find which draw is wrong. |
| `R300_DUMP=path` | Full per-draw state plus register trace, and dumps of textures and render targets (`path.NN.*.bin`). |
| `R300_RINGDUMP=path` | Raw command-ring contents, packet by packet, with indirect buffers marked. |
| `R300_SURFWATCH=1` | Log CPU accesses to the VRAM range the driver maps through a `SURFACE` register (e.g. depth readback for picking). |
| `R300_SYNC=1` | Flush to Metal after every draw instead of batching (isolates ordering bugs). |
| `R300_CPU_VS=1` | Run every vertex program in the CPU interpreter instead of on the GPU. |

**The device, the ring and the backends:**

| Variable | Effect |
|---|---|
| `PPCGPU_CP_SYNC=1` | Run the command ring synchronously in the guest's `WPTR` write, as before the CP thread. The first thing to try if a graphics bug appeared with it. |
| `PPCGPU_ASYNC_FENCE=0`, `1` or `2` | Fence (scratch register) completion: 0 synchronous, 1 always deferred until the GPU finishes, 2 (default) wait briefly, then defer. |
| `PPCGPU_FENCE_WAIT_US=n` | How long mode 2 waits for the GPU before deferring (default 250). |
| `PPCGPU_SPLIT=0` | Metal: on a read-after-write hazard, wait for the batch instead of splitting it into a new command buffer ordered by a shared event. |
| `PPCGPU_CSQ=busy` or `idle` | Force the command-queue status reply (default: real occupancy). |
| `PPCGPU_VK_CHECK=1` | Vulkan backend: log textures that changed in VRAM without the backend being told, and CPU writes over rendering not yet written back. |
| `PPCGPU_VK_DEVICE=n` | Vulkan backend: use Vulkan device number *n* instead of the first discrete (else integrated) GPU. |
| `PPCGPU_TRAFFIC=1` | Once a second: MMIO reads and writes, ring dwords, type-0 registers and draws. It shows how the guest talks to the card. |
| `PPCGPU_SEQ_LOG=1` | Packet sequence log (`/tmp/gpu_seq.log`), including 2D blits (`BBMRAW`) and 3D (`R3D`) lines. |
| `PPCGPU_DEBUG_LOG=1` | Every register access, to `/tmp/gpu_all_access.log`. Very slow. |
| `PPCGPU_DIAG=1` | Bring-up diagnostics from the reverse-engineering days (CRC scans, VRAM probes, register audits). Slow. |
| `QEMU_COCOA_SRGB=1` | Exact sRGB colour conversion in the Cocoa UI (slower). |
| `QEMU_CURSOR_DEBUG=1` | Log hardware-cursor layer geometry changes in the Cocoa UI. |
| `QEMU_PPC_NDRV=path` | Use a different NDRV (set by `ppcosx run`). |

**Tracing a guest that stops or waits** (these name what the guest is
stuck on):

| Variable | Effect |
|---|---|
| `POWEREMU_STALL_TRACE=1` | After 4 s without a draw: fences, ring pointers, interrupts, where write-backs land, and the last 256 register accesses. |
| `POWEREMU_POLL_TRACE=1` | Which registers the guest reads over and over. |
| `POWEREMU_FENCE_TRACE=1` | Scratch (fence) register values as the guest reads them. |
| `POWEREMU_WB_BE=1` | Write fences and the read pointer big-endian (the old, wrong order), for comparison. |

**The R200 path** (the inherited Radeon 9200 model; `ppcosx` doesn't use
it): `PPCGPU_R200_DIRECT=0`, `PPCGPU_ASYNC_DRAW=1`, `PPCGPU_VP=0`,
`PPCGPU_VP_MAP=0|1|2`, `PPCGPU_VERIFY_FETCH=1`, `PPCGPU_NO_TILING=1`,
`PPCGPU_TEXLOG=1`, `PPCGPU_TEXDUMP=1`, `PPCGPU_TRACETEX=fmt:w:h[:agp]`,
`PPCGPU_SPOTLOG=1`, `PPCGPU_ZCHECK=1`, `PPCGPU_ZDEBUG=1`,
`POWEREMU_TEX_TRACE=1`, `POWEREMU_VP_TRACE=1`, `POWEREMU_YUV_TRACE=1`
and `PPCGPU_WINDOWS=1|2` (window tracking). The comment next to each
`getenv` in `ppc_mac_gpu.c` or `ppc_mac_gpu_metal.m` says what it does.
`POWEREMU_GPU_SELFTEST=1` and `POWEREMU_GPU_REPLAY=file` run the
paravirtual GPU's self-test or replay a capture, then exit.

**The PowerPC CPU:**

| Variable | Effect |
|---|---|
| `PPC_STRICT_FP=1` | Turn off the host-FPU fast path for scalar floating point (always softfloat). |
| `PPC_TLBIE=page` | `tlbie` flushes only the named page instead of the whole TLB. |
| `PPC_FAULT_WATCH=lo-hi` | Log user-mode DSI/ISI faults at addresses in [lo, hi] (hex) to `/tmp/ppc_fault.log`, with registers and the code around NIP and LR. |

The device's read-only `trace` property lists which of the trace
variables are set.

`ppcosx run --trace-gpu` enables QEMU's `ppc_mac_gpu_*` trace events (every
register access) into `vm/gpu-trace.log`. It's large and slow, but complete.

## Profiling

Without any switches, `vm/gpu-trace.log` gets two lines a second while
the GPU is busy:

```
ppc-mac-gpu rate: 0.0 flips/s, 0.0 present-ops/s, 725 draws/s (63% GPU vertex programs), 268 2D ops/s, 48 flushes/s, GPU wait 0.5%
ppc-mac-gpu ring: 321 submits/s, 0 catch-ups/s
```

*GPU wait* is the share of time spent waiting for Metal. *Catch-ups*
are guest register accesses that had to wait for the ring to finish
(see [How it works](HOW-IT-WORKS.md#the-command-processor-runs-on-its-own-thread)).
The registers that caused them are named in brackets. A steady non-zero
figure means lost parallelism.

For where the time goes, sample the running QEMU. On macOS:

```bash
sample $(pgrep -f qemu-system-ppc) 5 -file /tmp/qemu.sample
```

The emulated CPU is the thread running `tcg_cpu_exec` (its translated
code shows as `???`). Look at that thread's busy share and its top
functions: `helper_*` entries are guest instructions that go through C
helpers, and device functions there are time the guest can't run. The CP
thread is `ppc-gpu-cp`, and Metal work runs on
`com.Metal.CommandQueueDispatch`. Measure before guessing: past "GPU
slowness" has turned out to be Core Animation colour conversion on the
main thread, per-pixel GART reads, and fence polling.

## Driving the guest from scripts

`ppcosx run --monitor` (or `ppcosx install --monitor`) opens the QEMU
monitor on 127.0.0.1:4444 (HMP) and 4445 (QMP). `tools/vmctl.py` wraps it:

```bash
tools/vmctl.py shot /tmp/screen.png
tools/vmctl.py key meta_l-spc          # Cmd+Space: Spotlight
tools/vmctl.py type 'Terminal'
tools/vmctl.py key ret
tools/vmctl.py click 512 384           # add "right" for a right click
tools/vmctl.py dclick 512 384          # double click
tools/vmctl.py move 100 100
tools/vmctl.py drag 100 100 400 300    # press, move, release
tools/vmctl.py cmd 'info pci' [wait]   # any HMP command; wait = seconds for output
```

Clicks go through a USB tablet, in guest pixels at the current resolution.
An installed Tiger scales tablet input by 1.1775 about the centre, which
`vmctl` undoes; the installer DVD doesn't, so use `VMCTL_SCALE=1` there. The
screen size comes from the VM; `VMCTL_RES=WxH` overrides it.

Useful HMP commands: `xp /2wx 0xa000ff0c` reads the hardware cursor
position (the MMIO BAR is at 0xA0000000 with the default `--vram 128`;
`info pci` shows where it is), and `info registers` samples the
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
* Never guess that a write-back address is system RAM. 0x07C24000 in guest
  RAM is kernel code.
* QEMU 10.0 takes the BQL for **every** MMIO access from TCG. A register
  that must not wait for a device thread needs
  `memory_region_enable_lockless_io()` (backported into the fork).
* TCG runs guest code without the BQL, even in round-robin mode (32-bit
  PPC has no MTTCG). A device thread that holds the BQL therefore still
  runs in parallel with the guest.
* AltiVec registers are stored in host byte order: host byte *j* is
  PowerPC byte 15 − *j*. A PowerPC permute that picks byte *s* of vA:vB
  is a lookup of index 31 − *s* in the table (vB, vA).
* Metal aborts the whole process on a linear texture view whose rows are
  longer than `bytesPerRow`. Validate views before making them.
* MoltenVK does not order framebuffer (input attachment) reads between
  draws. Without a by-region barrier per draw, blended shadows, menus and
  text leave garbage.
* Vulkan: write back only the rectangles draws touched, never whole
  images, or CPU 2D blits into the same buffer get undone.
