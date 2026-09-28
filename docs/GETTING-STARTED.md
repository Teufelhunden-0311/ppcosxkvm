# Getting started

This walks through everything from a fresh clone to a Tiger desktop with 3D
acceleration. If something goes wrong, see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 1. What you need

* **An Apple Silicon Mac** (M1 or later) on a recent macOS. Intel Macs
  aren't tested.
* **Homebrew**: <https://brew.sh>.
* **Xcode Command Line Tools.** `setup` starts the installer if they're
  missing. The full Xcode app isn't needed.
* **About 25 GB free**: roughly 1.5 GB for the QEMU build, plus the guest
  disk (it grows as you use it, 40 GB maximum by default).
* **Mac OS X for PowerPC**, which you provide. Either:
  * a **Tiger (10.4) install DVD image**: `.iso`, `.cdr`, `.dmg` or `.toast`.
    Use a *retail* DVD (black "X" or the 10.4 "Universal" DVD). The grey
    discs that shipped with a specific Mac often refuse to install on
    other models. **or**
  * an **already installed PowerPC OS X disk image** from another emulator,
    such as a UTM VM (`.utm`), VMware (`.vmdk`), VirtualBox (`.vdi`), or a raw
    `.img`/`.qcow2`.

For the best result, update the guest to **10.4.11** (the "Mac OS X 10.4.11
Combo Update (PPC)"). That's the version everything is tested on.

## 2. Install ppcosx

Paste this into Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/linuxkid473/ppcosxkvm/main/install.sh | bash
```

The installer:

1. checks that this is a Mac with the Command Line Tools and Homebrew (it
   tells you how to get whichever is missing, then you re-run it),
2. downloads the project into `~/.ppcosx` (set `PPCOSX_HOME` to choose
   another folder),
3. `brew install`s the build tools and libraries QEMU and the GPU backends
   need (ninja, pkgconf, glib, pixman, libslirp, shaderc, SPIRV-Cross,
   glslang, the Vulkan headers and loader, MoltenVK; only the missing ones),
4. fetches the QEMU fork (a shallow git submodule, several hundred MB) and
   builds `qemu-system-ppc` and `qemu-img`: a few minutes the first time,
5. adds the `ppcosx` command: a link in Homebrew's `bin` folder, which is
   already on your PATH, or else in `~/.local/bin`, added to your shell
   profile. If the command isn't found afterwards, open a new terminal window.

Running the one-liner again, or `ppcosx update`, updates to the latest
version and rebuilds what changed. `ppcosx unlink` removes the command, and
deleting `~/.ppcosx` removes everything, **including your VMs in
`~/.ppcosx/vm`**, so copy those out first.

### Manual install (for development)

```bash
git clone https://github.com/linuxkid473/ppcosxkvm.git
cd ppcosxkvm
./ppcosx setup
./ppcosx link        # optional: put this checkout's ppcosx on your PATH
```

Don't use `git clone --recursive`. It would also download QEMU's own nested
submodules (EDK2, OpenSSL and more, several GB) that this project doesn't
need; `setup` fetches just the QEMU fork. Without `link`, type `./ppcosx`
from the checkout wherever these docs say `ppcosx`. Build logs are in
`qemu/build/ppcosx-*.log`.

## 3a. Install Tiger from a DVD image

```bash
ppcosx install ~/Downloads/MacOSX-Tiger.iso
```

This creates an empty 40 GB disk at `vm/macosx.qcow2`, then boots the DVD in a
window. `--size 60G` picks a different size. A `.dmg` is first converted
once to a raw `.cdr` in `vm/`, because QEMU can't read compressed disk
images.

In the installer:

1. Choose a language and click through to the installer's first screen.
2. From the **Utilities** menu, open **Disk Utility**.
3. Select the **QEMU HARDDISK** in the list on the left, open the **Erase**
   tab, choose **Mac OS Extended (Journaled)**, name it (e.g. *Macintosh
   HD*), and click **Erase**.
4. Quit Disk Utility, and you're back in the installer. Continue, and pick
   the new volume.
5. Optional but much faster: click **Customize** and untick *Printer
   Drivers*, *Additional Fonts* and *Language Translations*.
6. Wait. A full install is roughly 30–60 minutes under emulation. The
   progress bar can sit still for minutes at a time, which is normal.
7. When the installer restarts the machine, the window closes (the
   installer runs with QEMU's `-no-reboot`).

The installer uses a plain framebuffer, not the Radeon. It doesn't need 3D,
and this is the configuration the Tiger installer is known to work with.

## 3b. …or bring an existing disk

```bash
ppcosx import ~/VMs/Tiger.vmdk          # .vmdk .qcow2 .vdi .vhd .img
ppcosx import ~/Library/Containers/com.utmapp.UTM/Data/Documents/Tiger.utm
```

The image is **copied** into `vm/macosx.qcow2`; your original is never
modified. For a `.utm` bundle, the largest disk in its `Data/` folder is
used. `--as vm/other.qcow2` imports under a different name (boot it with
`--disk`), and `--force` replaces an existing `vm/macosx.qcow2`.

The disk has to contain **PowerPC** Mac OS X. An Intel ("x86") OS X disk
won't boot on this emulated G4.

## 4. Boot

If you installed from an original 10.4 DVD, update to 10.4.11 first. The
Radeon driver in 10.4.0 (build 8A428) panics on the emulated card. Boot
with the plain framebuffer and the Combo Update inserted, run the Setup
Assistant, install the update, then shut down:

```bash
ppcosx run --vga --attach-dvd ~/Downloads/MacOSXUpdCombo10.4.11PPC.dmg
```

Then boot with the Radeon:

```bash
ppcosx run
```

The first boot after an install runs the Setup Assistant (the welcome movie,
then account creation), which can take a few minutes. Then check the
acceleration: **Apple menu → About This Mac → More Info… → Graphics/Displays**
should say **ATI Radeon 9700 Pro**, with *Quartz Extreme: Supported* and
*Core Image: Supported*.

Things to know:

* **Mouse capture.** Click in the window to use the guest. **Ctrl+Option+G**
  gives the mouse back to macOS.
* **Shutting down.** Use **Apple menu → Shut Down** in the guest, then the
  window closes. Closing the window or pressing Cmd+Q is like pulling the
  plug: fine in an emergency, but journaled HFS+ will have to replay its
  journal next boot.
* **Something looks wrong?** Boot with `ppcosx run --vga`. That's the plain
  framebuffer with no Radeon, useful for telling a graphics problem from
  anything else.

## 5. Next steps

* Take a snapshot of the clean install before experimenting:
  `ppcosx snapshot save fresh-install` (with the VM shut down).
* See [USAGE.md](USAGE.md) for all options: memory, video memory,
  resolution, SSH forwarding, throwaway sessions and more.
* Optionally give it the real card's ROM: [ROM.md](ROM.md).
