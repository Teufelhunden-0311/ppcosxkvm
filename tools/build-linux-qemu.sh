#!/bin/bash
# Build the prebuilt QEMU that "ppcosx setup" downloads on Linux, as a
# tarball: tools/build-linux-qemu.sh OUT.tar.xz
#
# Needs the build dependencies (see APT_DEPS in ppcosx) and the qemu/
# submodule checked out.  The GitHub workflow .github/workflows/
# qemu-linux.yml runs this on Ubuntu 24.04 (x86_64 and arm64) and
# attaches the result to the release "qemu-<first 12 of the qemu commit>".
#
# Layout: ppcosx-qemu/{bin/qemu-system-ppc, bin/qemu-img, lib/, share/pc-bios/,
# VERSION (the qemu commit)}.  lib/ has Debian's libshaderc.so.1, which
# links glslang and SPIRV-Tools in (other distributions split them and
# name it libshaderc_shared.so.1), so the build runs on those too; the
# binaries find it through RUNPATH $ORIGIN/../lib (patchelf).
set -euo pipefail

out=$(realpath -m "${1:?usage: $0 OUT.tar.xz}")
repo=$(cd "$(dirname "$0")/.." && pwd)
qemu="$repo/qemu"
build="$qemu/build-dist"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

[ -f "$qemu/configure" ] || { echo "qemu/ is not checked out" >&2; exit 1; }

# QEMU's configure wants a Python with distlib.
venv="$build/pyvenv"
rm -rf "$build"
mkdir -p "$build"
python3 -m venv "$venv"
"$venv/bin/python3" -m pip install -q distlib

# dtc:werror: see setup_build in ppcosx (the bundled dtc's own -Werror).
# No VNC JPEG or bzip2 (.dmg images): Ubuntu's libjpeg.so.8 and
# libbz2.so.1.0 are named otherwise elsewhere (Fedora), and ppcosx uses
# neither.
(cd "$build" && ../configure --python="$venv/bin/python3" \
    --target-list=ppc-softmmu --disable-docs --disable-sdl \
    --enable-gtk --enable-pa --enable-slirp --disable-werror -Doptimization=2 \
    -Ddtc:werror=false --disable-vnc-jpeg --disable-bzip2)
ninja -C "$build" -j "$(nproc)" qemu-system-ppc qemu-img

d="$stage/ppcosx-qemu"
mkdir -p "$d/bin" "$d/lib" "$d/share/pc-bios"
cp "$build/qemu-system-ppc" "$build/qemu-img" "$d/bin/"
strip "$d/bin/"*
shaderc=$(ldd "$build/qemu-system-ppc" | awk '$1 == "libshaderc.so.1" { print $3 }')
[ -f "$shaderc" ] || { echo "qemu-system-ppc does not use libshaderc.so.1" >&2; exit 1; }
cp -L "$shaderc" "$d/lib/"
patchelf --set-rpath '$ORIGIN/../lib' "$d/bin/qemu-system-ppc"
# ppcosx passes its own firmware first (-L firmware/...); these cover
# what QEMU itself looks up.
cp -r "$qemu/pc-bios/keymaps" "$d/share/pc-bios/"
for f in openbios-ppc qemu_vga.ndrv; do
    [ -f "$qemu/pc-bios/$f" ] && cp "$qemu/pc-bios/$f" "$d/share/pc-bios/"
done
git -C "$repo" rev-parse HEAD:qemu > "$d/VERSION" 2>/dev/null \
    || git -C "$qemu" rev-parse HEAD > "$d/VERSION"

tar -C "$stage" -cJf "$out" ppcosx-qemu
echo "wrote $out ($(du -h "$out" | cut -f1), qemu $(cat "$d/VERSION"))"
