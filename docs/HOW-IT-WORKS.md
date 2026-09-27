# How it works

The idea: emulate a graphics card that Mac OS X **already has a driver
for**, accurately enough that Apple's own ATI driver runs it unmodified.
The card is the ATI Radeon 9700 PRO (R300, PCI ID 1002:4E44), the first
Mac card with the programmable fragment shaders Core Image requires. The
older Radeon 9000/9200 (R200) can do Quartz Extreme but not Core Image.

No guest-side drivers are added or patched. What Tiger runs is exactly
what it would run on a Power Mac G4 with that card.

## The pieces

```
guest  │ WindowServer (Quartz Extreme)  Core Image   OpenGL apps
       │           │                        │            │
       │   ATIRadeon9700GLDriver.bundle / ATIRadeon9700GA.plugin
       │           │                                      │
       │   ATIRadeon9700.kext ── MMIO registers, command ring, GART
───────┼───────────┼──────────────────────────────────────┼──────────
QEMU   │   ati-radeon-9700 device (hw/display/ppc_mac_gpu.c)
       │     ├─ PCI config, BARs (VRAM apertures, MMIO), AGP
       │     ├─ CP: ring buffer, indirect buffers, PM4 packets,
       │     │   scratch/fence write-backs, 2D blits
       │     ├─ R300 3D state (hw/display/r300/r300_state.c)
       │     ├─ vertex programs (PVS) interpreted on the CPU (r300_pvs.c)
       │     ├─ fragment programs (US) → Metal Shading Language (r300_us.c)
       │     └─ draw assembly: primitives, index buffers, point sprites (r300_draw.c)
       │   Metal backend (hw/display/ppc_mac_gpu_metal.m)
       │     └─ render targets and textures in VRAM ⇄ Metal textures
───────┼──────────────────────────────────────────────────────────
host   │ Apple Silicon GPU
```

### Boot chain

1. **OpenBIOS** (`firmware/radeon/openbios-ppc`) is the Mac's Open
   Firmware. OpenBIOS only builds a display node, and loads the display
   driver, for PCI IDs in a built-in table. That table's QEMU VGA entry is
   patched to 1002:4E44, so the Radeon gets a node named `QEMU,VGA`
   (see `firmware/src/patch-openbios.py`).
2. **The boot command** that `ppcosx run` passes (`-prom-env boot-command=…`)
   finds that node, `/pci@f2000000/QEMU,VGA@e`, and adds what the card's own
   FCode would have: `VRAM,totalsize`, and the 9700 PRO's identity
   (`model = "ATY,R300"`, `ATY,Rom#`, `ATY,Card#`, `ATY,Fcode`). Tiger's
   System Profiler turns `ATY,R300` into "ATI Radeon 9700 Pro" through a
   table in its display reporter. `ppcosx` pins the Radeon to PCI slot
   0x0E so that path is always right: `find-device` fails silently if
   the node sits anywhere else.
3. **The NDRV** (`firmware/radeon/qemu_vga_hwc.ndrv`, the QemuMacDrivers VGA
   driver with a hardware cursor added) drives the framebuffer, both for
   the boot screen and as the IONDRVFramebuffer. It's matched by the node's
   `name`/`compatible`, which is why those stay `QEMU,VGA`.
4. **`ATIRadeon9700.kext`** matches the PCI ID (it's first in Tiger's
   IOPCIMatch list), takes over acceleration, and loads the GL and GA
   (2D) plug-ins.

### Command processing

The ATI driver doesn't touch 3D registers directly. It writes packets into
a **ring buffer** in memory and advances the write pointer. The device
parses them: PM4 type-0 packets (register writes), type-3 packets (draws,
blits, indirect buffers, clears) and type-2 (padding). Completion goes
back through **write-backs** (the ring read pointer, scratch registers,
fences) into memory the driver polls.

Buffers can live in VRAM or in system memory seen through the **GART**
(the AGP/PCI graphics address remapping table). On R300 the table base is
register 0x0AB0, not the R200's 0x1D8. Getting that wrong makes every
write-back miss, and the driver declares the chip hung.

### 3D translation

For each draw, the device snapshots the R300 state and:

* **Vertex processing (PVS):** the driver's vertex program runs through a
  CPU interpreter of the R300 vertex shader ISA (including flow control),
  giving clip-space positions and varyings.
* **Fragment processing (US):** the R300 fragment program (texture
  instructions plus RGB/alpha ALU instructions) is translated to a Metal
  fragment shader, compiled once and cached by program hash.
* **Fixed function:** blending, alpha test, depth/stencil (done in the
  shader against a depth attachment), culling, polygon offset and mode,
  scissors and cliprects, fog, user clip planes, colour masks and ROPs.
* **Render targets and textures** live in emulated VRAM in the card's
  byte order. They're uploaded to Metal textures on use, and results are
  written back to VRAM so the CPU, 2D blits and scanout all see them.
  The data is stored big-endian (the CPU's view), so 32-bit texels decode
  as `abgr`, and `COLOR_ENDIAN` decides the byte order of stored pixels.
* **MSAA:** a multisampled buffer stores sample *k* of row *y* at row
  *y·n+k*, the same footprint the driver allocates. Each sample is drawn
  with shifted geometry, and `RB3D_AARESOLVE` averages them.

### Presenting

Quartz Extreme composites into a back buffer and presents it by drawing one
full-screen **point sprite** that samples the back buffer into the scanout
buffer. The scanout then takes the 3D pitch. OpenGL swaps go through
`RB3D_AARESOLVE`. QEMU's display reads the scanout from VRAM, and
`ui/cocoa.m` tags the frame with the window's colour space, so the host
doesn't spend most of its time colour-converting.

## Why QEMU, why TCG

There's no PowerPC hardware to virtualise on, so the G4 CPU is emulated by
QEMU's TCG JIT. The GPU work isn't: draws run on the host GPU through
Metal. That's why the desktop stays smooth while CPU-heavy apps are
slow.

## Limitations

* **One CPU, emulated.** The guest is a single-CPU G4. Apps bound by the
  CPU run at old-Mac speeds.
* **Resolution.** The Radeon mode is tested at 1024×768. Other `--res`
  sizes are experimental.
* **Tiling** (macro/micro tile bits) is ignored. That's consistent as long
  as only the GPU touches tiled buffers, which is true for everything
  tested.
* **VRAM in System Profiler** shows the size of the VRAM BAR, which
  holds two apertures onto VRAM: twice `--vram`, so 256 MB at the
  default 128.
* **Leopard** (10.5) has an R300 driver too, but hasn't been tested.
* Not implemented: video decode acceleration (`ATIRadeon9700VADriver`),
  TV out, dual-head.
