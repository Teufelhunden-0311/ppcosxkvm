#!/usr/bin/env python3
"""Make firmware/radeon/openbios-ppc from UTM 4.7.5's OpenBIOS.

Two 4-byte changes:

* OpenBIOS builds a display node (QEMU,VGA) and attaches the QEMU NDRV only
  for PCI IDs in its built-in VGA table.  This swaps the table's QEMU VGA
  entry (1234:1111) for the Radeon 9700 PRO (1002:4E44), so the emulated
  Radeon gets the display node and the NDRV instead.

* The mac99 PCI host's "ranges" property advertises a 256 MB memory window
  (0x80000000-0x8fffffff), but QEMU's hole is 1 GB and OpenBIOS assigns the
  Radeon's VRAM and register BARs above that window (0x90000000,
  0xa0000000).  Tiger ignores this; Leopard's IOPCIFamily drops BARs that
  fall outside "ranges", so ATIRadeon9700.kext finds no register BAR and
  panics.  This widens the advertised window to 1 GB, matching the hole.

    python3 patch-openbios.py <UTM openbios-ppc> <output> [pci-id]

  With "pci-id" (four hex digits, e.g. 4966) the VGA table gets that device
  of vendor 1002 instead: firmware/jaguar/openbios-ppc is made with 4966,
  the Radeon 9000 PRO that Mac OS X 10.2's ATIRadeon8500.kext drives.

The input is firmware/vga/openbios-ppc, a copy of
UTM.app/Contents/Resources/qemu/openbios-ppc from UTM 4.7.5.
"""
import hashlib
import sys

PATCHES = [
    # offset,  old,        new,        what
    (0x30678, "12341111", "10024e44", "VGA table PCI ID -> Radeon 9700 PRO"),
    (0x2e144, "10000000", "40000000", "mac99 PCI memory window in 'ranges' -> 1 GB"),
]
UTM_SHA1 = "95d46d815fe3cf04c498ea551e0f3bb66b7785f7"

src, dst = sys.argv[1], sys.argv[2]
if len(sys.argv) > 3:
    dev = sys.argv[3].lower().zfill(4)
    PATCHES[0] = (PATCHES[0][0], PATCHES[0][1], "1002" + dev,
                  "VGA table PCI ID -> Radeon 1002:" + dev.upper())
data = bytearray(open(src, "rb").read())
if hashlib.sha1(data).hexdigest() != UTM_SHA1:
    print("warning: input is not UTM 4.7.5's openbios-ppc; the offsets may differ")
for offset, old, new, what in PATCHES:
    old, new = bytes.fromhex(old), bytes.fromhex(new)
    if data[offset:offset + 4] != old:
        sys.exit("%s: expected %s at 0x%x, found %s" % (
            what, old.hex(), offset, data[offset:offset + 4].hex()))
    data[offset:offset + 4] = new
open(dst, "wb").write(data)
print("wrote %s (sha1 %s)" % (dst, hashlib.sha1(data).hexdigest()))
