# Troubleshooting

Start with `ppcosx doctor`. It checks most of what's below.

## Setup and building

**`xcode-select: note: install requested`, then setup stops.** Finish the
Command Line Tools install in the dialog, then run `ppcosx setup` again.

**`Homebrew is required`.** Install it from <https://brew.sh>, open a *new*
terminal window (so `brew` is on your `PATH`), and re-run setup.

**`qemu/ is empty` / `could not fetch the qemu submodule`.** Fetching the
QEMU fork failed. Check your network, then run
`git submodule update --init --depth 1 qemu` and `ppcosx setup`.

**configure or the build fails.** Read the log the error names
(`qemu/build/ppcosx-configure.log` or `ppcosx-build.log`). Common causes:

* a Homebrew package is broken or half-upgraded: `brew update && brew upgrade`, then re-run setup;
* stale build files after a big `git pull`: `rm -rf qemu/build && ppcosx setup`.

## Installing

**The DVD doesn't boot (you see an Open Firmware prompt `0 >`, or the
window stays black).**

* Make sure it's a **PowerPC** Mac OS X DVD: 10.4 retail or 10.4
  Universal. Intel-only 10.4 DVDs (the grey ones from 2006 Intel Macs)
  won't boot.
* Some `.dmg` or `.toast` files are compressed or multi-session in ways QEMU
  can't read. Convert on the Mac:
  `hdiutil convert Tiger.dmg -format UDTO -o Tiger` gives `Tiger.cdr`.
  Install from that.
* Check the image isn't truncated: a Tiger DVD image is 2.5–8 GB.

**"Mac OS X cannot be installed on this computer."** It's a machine-specific
(grey) disc. Use a retail one.

**The installer doesn't list the disk.** It needs erasing first: Disk
Utility → select the QEMU HARDDISK → Erase → Mac OS Extended (Journaled).

## Booting

**Black window or a stuck grey Apple.** Boot with `ppcosx run --verbose`
to see where it stops. Then try `ppcosx run --vga`:

* if `--vga` boots, the problem is in the Radeon path. Please open an
  issue with the last lines of the verbose boot and `vm/gpu-trace.log`.
* if `--vga` doesn't boot either, it's the disk or the OS install.

**Kernel panic mentioning `ATIRadeon9700`.** On 10.4.0 (the original DVD,
build 8A428) this is expected: boot with `--vga` and install the 10.4.11
Combo Update (see [GETTING-STARTED.md](GETTING-STARTED.md#4-boot)). On
10.4.11, please report it with a photo or screenshot of the panic text. As
a workaround, `--vga` still boots.

**`a VM is already running on macosx.qcow2`.** Two VMs writing one disk
would corrupt it, so QEMU locks the disk while a VM uses it. Shut the
other one down first. This applies to `--snapshot` too: QEMU refuses to
open a disk another VM holds ("Failed to get shared "write" lock").

**`port 4444 is in use`.** Another VM is running with `--monitor`. Close it,
or leave `--monitor` off.

## Inside the guest

**System Profiler doesn't say "ATI Radeon 9700 Pro".** You probably booted
with `--vga`. Without it, check the boot log line
`Booting … with the ATI Radeon 9700 PRO`. Running an old copy of the
launcher? `git pull` and try again.

**VRAM (Total) says 256 MB.** Expected: System Profiler reports the size
of the card's memory window (PCI BAR 0). It holds two apertures onto
VRAM, so it's twice `--vram`: 256 MB at the default 128.

**Slow.** It's a whole PowerPC Mac interpreted in software on one host
core. Things that help: close apps you don't need in the guest, give it
`--ram 1536` or more, and turn off Spotlight indexing
(`sudo mdutil -i off /` in the guest's Terminal). Video and other AltiVec
code is much faster on an Apple Silicon or other ARM64 host than on x86
Linux, where the AltiVec speed-ups don't apply.

**Graphics glitches, or a 3D app that hangs, that didn't happen before an
update.** The Radeon's command processor now runs on its own thread, in
parallel with the guest. To rule that out, run it the old way:

```bash
PPCGPU_CP_SYNC=1 ppcosx run
```

If that fixes it, please open an issue saying so, with the app and
`vm/gpu-trace.log`. `PPCGPU_ASYNC_FENCE=0` (fences completed at once)
and `R300_SYNC=1` (no draw batching) narrow things down further.

**Video or an app looks wrong only on the Radeon, or a filter computes
wrong numbers.** The AltiVec instructions translated to NEON are checked
by `qemu/tests/ppc-vmx/run.py`. If you find a program that computes
differently here than on a real Mac, please report it with the program
and what it does.

**The mouse pointer and the guest's cursor don't line up.** Release and
re-capture the mouse (Ctrl+Option+G, then click). In the Radeon mode the
pointer is an absolute tablet, so it should track 1:1 at 1024×768.

**Safari can't open modern websites.** Tiger's TLS is too old for most of
today's HTTPS. See [USAGE.md](USAGE.md#getting-files-in-and-out) for other
ways to move files.

## Reporting a bug

Please include:

* the output of `ppcosx doctor`,
* the exact `ppcosx` command,
* your Tiger version (Apple menu → About This Mac),
* `vm/gpu-trace.log` for graphics problems, and a screenshot,
* whether `PPCGPU_CP_SYNC=1` changes anything, for graphics problems.
