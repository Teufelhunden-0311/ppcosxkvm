#!/usr/bin/env python3
"""Make firmware/radeon/openbios-ppc from UTM 4.7.5's OpenBIOS.

OpenBIOS builds a display node (QEMU,VGA) and attaches the QEMU NDRV only
for PCI IDs in its built-in VGA table.  This swaps the table's QEMU VGA
entry (1234:1111) for the Radeon 9700 PRO (1002:4E44), so the emulated
Radeon gets the display node and the NDRV instead.

    python3 patch-openbios.py <UTM openbios-ppc> <output>

The input is firmware/vga/openbios-ppc, a copy of
UTM.app/Contents/Resources/qemu/openbios-ppc from UTM 4.7.5.
"""
import hashlib
import sys

OFFSET = 0x30678
OLD = bytes.fromhex("12341111")
NEW = bytes.fromhex("10024e44")
UTM_SHA1 = "95d46d815fe3cf04c498ea551e0f3bb66b7785f7"

src, dst = sys.argv[1], sys.argv[2]
data = bytearray(open(src, "rb").read())
if hashlib.sha1(data).hexdigest() != UTM_SHA1:
    print("warning: input is not UTM 4.7.5's openbios-ppc; the offset may differ")
if data[OFFSET:OFFSET + 4] != OLD:
    sys.exit("expected %s at 0x%x, found %s" % (OLD.hex(), OFFSET,
                                                data[OFFSET:OFFSET + 4].hex()))
data[OFFSET:OFFSET + 4] = NEW
open(dst, "wb").write(data)
print("wrote %s (sha1 %s)" % (dst, hashlib.sha1(data).hexdigest()))
