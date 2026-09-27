# Using ppcosx

`ppcosx` is the one command for everything. The one-line installer puts it
on your PATH. In a manual checkout, run `./ppcosx link` once, or type
`./ppcosx`.

**Shorthand:** a bare `ppcosx` boots the VM, and any run option works
without the word `run`: `ppcosx --vga` is `ppcosx run --vga`.

## Commands

| Command | What it does |
|---|---|
| `ppcosx setup` | Install build dependencies and build QEMU. Safe to re-run; it updates the build after a `git pull`. |
| `ppcosx doctor` | Check the host, the build, the firmware checksums, your disk and ROM. |
| `ppcosx install <dvd> [--size 40G] [--disk PATH]` | Boot a Mac OS X install DVD image (`.iso` `.cdr` `.dmg` `.toast`) with an empty disk attached. See [GETTING-STARTED.md](GETTING-STARTED.md#3a-install-tiger-from-a-dvd-image). |
| `ppcosx import <image> [--as PATH] [--force]` | Copy an existing PowerPC OS X disk (`.qcow2` `.vmdk` `.vdi` `.vhd` `.img`, or a `.utm` bundle) to `vm/macosx.qcow2`. |
| `ppcosx` / `ppcosx run [options]` | Boot the disk with the emulated Radeon 9700 PRO. |
| `ppcosx --vga` | Boot with a plain framebuffer and no Radeon: safe mode. |
| `ppcosx update` | `git pull` the latest version and rebuild. Your VMs aren't touched. |
| `ppcosx link` / `ppcosx unlink` | Add or remove the `ppcosx` command on your PATH. |
| `ppcosx rom <file>` / `rom --remove` | Install or remove an optional Radeon 9700 PRO ROM ([ROM.md](ROM.md)). |
| `ppcosx new-disk [size] [path]` | Create an empty qcow2 disk (default 40G at `vm/macosx.qcow2`). |
| `ppcosx snapshot list \| save NAME \| restore NAME \| delete NAME` | Disk snapshots. The VM must be shut down. |

## `run` options

| Option | Default | Meaning |
|---|---|---|
| `--disk PATH` | `vm/macosx.qcow2` | Disk image to boot. |
| `--ram MB` | 1024 | Guest memory, 256–2048. The Power Mac G4 (mac99) tops out at 2 GB. |
| `--cpu-mhz N` | 2000 | CPU speed Mac OS X is *told* (100–4000). Shown in About This Mac and checked by apps with minimum requirements. It doesn't change how fast the emulation actually runs. |
| `--vram MB` | 128 | Radeon video memory: 64, 128 or 256. The real 9700 PRO has 128. |
| `--res WxH` | 1024x768 | Initial screen size. The Radeon mode is tested at 1024×768; other sizes are experimental. |
| `--rom PATH` / `--no-rom` | `vm/roms/radeon9700.rom` if present | Radeon option ROM. |
| `--attach-dvd IMG` (or `--dvd`, `--cd`) | | Insert a DVD/CD image (`.iso` `.cdr` `.dmg` `.toast`), e.g. to install software from a disc. A `.dmg` is converted once to a raw `.cdr` in the VM folder (QEMU can't read compressed `.dmg`s). |
| `--verbose` | off | Text-mode ("verbose") boot instead of the grey Apple. Good for diagnosing hangs. |
| `--snapshot` | off | Throwaway session: all disk writes are discarded when QEMU exits. The disk must not be in use by another VM. |
| `--ssh-port N` | | Forward `127.0.0.1:N` on the host to the guest's SSH (turn on *Remote Login* in the guest's Sharing preferences). |
| `--monitor` | off | QEMU's monitor on `127.0.0.1:4444` (HMP) and `:4445` (QMP), for `tools/vmctl.py` and scripting. |
| `--trace-gpu` | off | Log every GPU register access to `vm/gpu-trace.log`. Very slow; for debugging only. |
| `-- ARGS…` | | Everything after `--` goes to QEMU unchanged. |

Examples:

```bash
ppcosx --ram 2048                           # more memory
ppcosx --snapshot                           # try something risky
ppcosx --attach-dvd ~/Discs/Photoshop7.dmg  # insert a disc image (.iso .dmg .cdr .toast)
ppcosx run --ssh-port 2222                  # then: ssh -p 2222 user@127.0.0.1
ppcosx run -- -serial stdio                 # extra QEMU flags
```

## Keyboard and mouse

* Click the window to capture the mouse; **Ctrl+Option+G** releases it.
* Keyboard shortcuts that QEMU's own menus use (such as Cmd+Q) may go to
  QEMU instead of the guest. Use the guest's menus if in doubt.
* In the Radeon mode the pointer is an absolute USB tablet plus a
  hardware cursor drawn by the emulated card.

## Files

Everything that's yours lives in the `vm/` folder of the install:
`~/.ppcosx/vm/` with the one-line installer (git ignores it, so updates
never touch it). `ppcosx help` prints the exact path. Set
`PPCOSX_VM_DIR=/some/other/folder` to keep it elsewhere, e.g. on an external
drive.

| Path | |
|---|---|
| `vm/macosx.qcow2` | The guest disk. Grows as it's used. |
| `vm/roms/radeon9700.rom` | Optional ROM, installed by `ppcosx rom`. |
| `vm/gpu-trace.log` | GPU log: first-use notices for 3D features and the texture formats seen. Rewritten on each boot. |
| `vm/dvd-*.cdr` | Raw copies of `.dmg` disc images, made by `--attach-dvd` and `ppcosx install`. Safe to delete; they're remade when needed. |

## Snapshots

qcow2 disks can hold snapshots of themselves. With the VM **shut down**:

```bash
ppcosx snapshot save before-update
ppcosx snapshot list
ppcosx snapshot restore before-update    # the disk goes back to that moment
ppcosx snapshot delete before-update
```

For a one-off experiment, `ppcosx run --snapshot` is simpler: nothing is
written to the disk at all.

## Getting files in and out

* **Network**: the guest has NAT networking out of the box. Safari (Tiger's
  is old, so many HTTPS sites fail), FTP and `curl` work for plain HTTP
  servers. A simple way to share a folder is `python3 -m http.server 8000`
  on the Mac, then `http://10.0.2.2:8000/` in the guest (10.0.2.2 is the
  host).
* **SSH/SFTP**: `--ssh-port 2222` plus *Remote Login* in the guest.
  Tiger's OpenSSH is old; from a modern Mac you may need
  `ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -p 2222 user@127.0.0.1`.
* **Disc images**: `hdiutil makehybrid -hfs -iso -o files.iso some-folder/`
  on the Mac, then `ppcosx --attach-dvd files.iso`.
