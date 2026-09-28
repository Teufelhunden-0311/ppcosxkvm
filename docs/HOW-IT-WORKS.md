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
       │     ├─ CP, on its own thread: ring buffer, indirect buffers,
       │     │   PM4 packets, scratch/fence write-backs, 2D blits
       │     ├─ R300 3D state (hw/display/r300/r300_state.c)
       │     ├─ vertex programs (PVS) → GLSL on the GPU, or a CPU
       │     │   interpreter for what that can't cover (r300_pvs.c)
       │     ├─ fragment programs (US) → GLSL (r300_us.c) → SPIR-V → MSL (r300_spirv.c)
       │     └─ draw assembly: primitives, index buffers, point sprites (r300_draw.c)
       │   Metal backend (hw/display/ppc_mac_gpu_metal.m)
       │     └─ render targets and textures in VRAM ⇄ Metal textures
       │   or Vulkan backend (hw/display/ppc_mac_gpu_vulkan.c)
       │     └─ images on the GPU, copied to/from VRAM on demand
───────┼──────────────────────────────────────────────────────────
host   │ Apple Silicon GPU (Metal, or Vulkan via MoltenVK), or a
       │ Linux GPU (Vulkan)
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

#### The command processor runs on its own thread

A real Radeon executes its ring while the CPU goes on running, and the
driver is written for that: it learns how far the card has got from the
read pointer and from fences, never from when its register writes
return. The device works the same way. The guest's write to
`CP_RB_WPTR` only records the new write pointer and wakes a thread,
`ppc-gpu-cp`, which carries out the ring. Meanwhile the emulated CPU
goes on building its next batch. Before this, the ring ran inside that
register write, on the emulated CPU's own thread, and the guest stood
still for every packet decoded, translated and handed to Metal.

How it stays correct:

* **One lock, as before.** The CP thread holds QEMU's big lock (the BQL)
  while it replays the ring, just as the emulated CPU did, so every
  device path keeps the serialisation it was written for: registers,
  Metal, interrupts, the display refresh. The parallelism comes from TCG
  running guest code *without* the BQL: the guest only waits when it
  touches a device.
* **Catch up before the guest looks.** Any other guest access to the
  card's registers or VRAM apertures first carries out whatever is left
  of the ring, on the accessing thread, then is served. That's exactly
  what the guest saw when the ring ran synchronously, so fences,
  read-pointer write-backs, 2D blits through registers and CPU readbacks
  stay in order. The exceptions have nothing to order: the `WPTR` write
  itself, reads of the read pointer (the card's progress, which is what
  the driver wants) and the hardware cursor.
* **Submitting never waits.** `CP_RB_WPTR` sits in a 4-byte MMIO region
  that's dispatched without the BQL
  (`memory_region_enable_lockless_io()`, backported from QEMU 10.1), so a
  submit doesn't wait for the CP thread to finish a batch.
* **Long batches share the lock.** Every 200 µs, between two packets, the
  CP thread publishes its progress as the read pointer and lets go of the
  BQL, so other devices, the display and further submits get in. If
  someone catches the ring up meanwhile, the thread sees the ring changed
  hands (an epoch counter) and drops the rest of its copy.

Tiger's driver never makes the ring catch up in normal use. The `ring:`
line in `vm/gpu-trace.log` counts submits and catch-ups every second,
and names the registers that forced any. `PPCGPU_CP_SYNC=1` runs the
ring synchronously again, as a fallback.

Buffers can live in VRAM or in system memory seen through the **GART**
(the AGP/PCI graphics address remapping table). On R300 the table base is
register 0x0AB0, not the R200's 0x1D8. Getting that wrong makes every
write-back miss, and the driver declares the chip hung.

### 3D translation

For each draw, the device snapshots the R300 state and:

* **Vertex processing (PVS):** the driver's vertex program is translated
  to GLSL (`r300_pvs_to_glsl`) and runs on the host GPU, in front of a
  generated post-transform stage. That covers triangles with smooth
  colours, which is nearly everything. The rest (and everything, with
  `R300_CPU_VS=1`) runs through a CPU interpreter of the R300 vertex
  shader ISA, including flow control. `tests/r300/test_gpuvs` checks that
  both paths agree. The GPU path is Metal only; Vulkan uses the
  interpreter.
* **Fragment processing (US):** the R300 fragment program (texture
  instructions plus RGB/alpha ALU instructions) is translated to GLSL,
  compiled to SPIR-V with shaderc and, for Metal, on to Metal Shading
  Language with SPIRV-Cross. The shader reads the colour and depth
  buffers it blends into through input attachments, which become Metal
  framebuffer fetch. Each program is compiled once and cached by its
  source.
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

### Metal and Vulkan

The device picks its backend with the `renderer` property (`ppcosx
--gpu metal|vulkan`, `--gpumetal`, `--gpuvulkan`). Metal is the default on
macOS, Vulkan elsewhere; asking for one the host can't provide fails
at startup with the reason.

Both backends run the same GLSL. Metal compiles it on to MSL; Vulkan
uses the SPIR-V directly, in a variant that reads shader-decoded texture
formats from a storage buffer of VRAM.

They differ in where the pixels live. Metal renders straight into VRAM:
render targets and most textures are linear texture views of the one
shared buffer that is also the guest's VRAM. Vulkan can't do that (an
image can't alias a buffer at the guest's pitch, and a discrete GPU's
memory isn't the CPU's), so:

* VRAM is host-visible Vulkan memory, the CPU's copy. The GPU only
  copies from and to it, and reads odd texture formats from it.
* Colour and depth buffers and textures are images on the GPU, cached
  by their VRAM range and layout.
* Every VRAM page has a write generation. CPU writes (the device's
  dirty log) and GPU writes (a draw into an image) stamp the pages they
  touch. An image with an older stamp than its range is copied from VRAM
  before use, after any newer rendering over that range is written back.
* What a batch renders is written back to VRAM when the batch is
  submitted, so fences, scanout and CPU reads see finished drawing
  exactly as with Metal.

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

## Keeping the emulated CPU fast

With one emulated CPU, anything the device or the emulator does on that
CPU's thread is time the guest doesn't get. Profiling (`sample <qemu
pid> 5` on macOS) showed a lot of it, and these changes to the fork give
it back:

* **The GPU works in parallel.** The command ring runs on its own thread
  (see [Command processing](#command-processing)).
* **Less per-draw work on the CPU.** Vertex programs run on the GPU.
  Fragment programs are translated once and cached by the registers the
  translator reads. GART and AGP memory is read a 4 KB page at a time
  rather than a pixel or a dword at a time.
* **AltiVec on NEON.** Stock QEMU runs AltiVec's byte shuffles through
  out-of-line helpers that loop over bytes, and QuickTime's decoders use
  them heavily. The fork adds a TCG vector operation, `tbl_vec` (a
  two-register byte table lookup, emitted as NEON `TBL`/`TBX` on Apple
  Silicon and other ARM64 hosts), and translates these to inline host
  instructions:
  * `vperm`, `vsldoi`
  * the merges `vmrgh[bhw]`/`vmrgl[bhw]`
  * the packs `vpku[hw]um`, and the saturating ones with `VSCR[SAT]` kept
  * the signed unpacks `vupk[hl]s[bh]`
  * the even/odd multiplies `vmul[eo][us][bh]` and the modulo
    multiply-sums `vmsum{ubm,mbm,uhm,shm}`, which become shifts and
    vector multiplies.

  In a benchmark, net of loop overhead, `vperm` is about 6× cheaper and
  the merges, `vsldoi` and packs about 4×. Hosts without `tbl_vec` (x86)
  keep the helpers.
* **AltiVec floats on the host FPU.** `vaddfp`, `vsubfp`, `vmaxfp`,
  `vminfp`, `vmaddfp`, `vnmsubfp`, `vrefp`, `vrsqrtefp`, `vcf[su]x` and
  `vct[su]xs` compute with NEON when every input and result is a normal
  number or zero. There, IEEE arithmetic and PowerPC's agree bit for bit.
  NaNs, infinities and denormals, whose handling depends on `VSCR[NJ]` and
  PowerPC's NaN rules, still go through softfloat. `vmaddfp` is about 3×
  faster.
* **Scalar floating point on the host FPU.** Inherited from the fork
  this project builds on: `fadd`, `fmul`, `fmadd` and the rest compute on
  the host in the state Mac OS X runs applications in (round to nearest,
  no FP exceptions enabled). `PPC_STRICT_FP=1` turns this off.
* **Host-side display.** `ui/cocoa.m` tags the frame with the window's
  colour space, so Core Animation doesn't spend the main thread
  colour-converting every frame.

`qemu/tests/ppc-vmx/run.py` checks every AltiVec change against scalar
references in a bare-metal guest and times them (see
[DEVELOPING.md](DEVELOPING.md#offline-tests)).

## Limitations

* **One CPU, emulated.** The guest is a single-CPU G4. Apps bound by the
  CPU run at old-Mac speeds. The *reported* speed is 2 GHz by default
  (`--cpu-mhz`; QEMU normally says 900 MHz) so that apps with minimum
  requirements, such as Aperture, see a capable Mac. Guest timing uses the
  separate timebase clock, so the reported figure doesn't affect behaviour.
* **It says it's a PowerBook.** By default the machine reports itself as a
  `PowerBook5,8` (`--model`): Mac OS X takes `hw.model` from the first
  entry of the firmware's root `compatible` property, and Aperture 1.5
  accepts a G4 only in a machine whose model starts with "PowerBook"
  (faster than 1.25 GHz). It checks nothing else about the hardware
  except OpenGL's `GL_ARB_fragment_program`. `--model default` restores
  the firmware's `PowerMac3,1`.
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
  TV out, dual-head. Video is decoded by the emulated CPU, with AltiVec
  on NEON (see above). The one AltiVec instruction QuickTime still sends
  through a slow helper is `vmhraddshs`.
* **AltiVec speed-ups need an ARM64 host.** On x86 Linux the converted
  instructions use QEMU's portable helpers: correct, but slower.
