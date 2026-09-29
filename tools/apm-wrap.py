#!/usr/bin/env python3
"""Put an Apple Partition Map in front of a bare HFS/HFS+ disc image.

A retail Mac OS X 10.5 (Leopard) install DVD image is a single HFS+ volume
with no partition map. A real Mac's Open Firmware boots that, but OpenBIOS
only boots a CD whose volume sits in an Apple_HFS partition, as on Tiger's
DVD: it drops to the Forth prompt with "No valid state has been set by load
or init-program". This writes a copy with a 32 KB partition map in front.

    apm-wrap.py check IMAGE      exit 0 if IMAGE is a bare HFS/HFS+ volume
    apm-wrap.py wrap SRC DST     write DST = partition map + SRC
"""
import os
import shutil
import struct
import sys

BS = 512
MAP_BLOCKS = 64         # driver descriptor + map; the volume starts at block 64


def bare_hfs(path):
    with open(path, 'rb') as f:
        head = f.read(1026)
    if len(head) < 1026 or head[:2] == b'ER':     # ER: already partitioned
        return False
    return head[1024:1026] in (b'H+', b'HX', b'BD')


def entry(start, count, name, ptype, status):
    return struct.pack('>2sHIII32s32sIII', b'PM', 0, 2, start, count,
                       name.encode(), ptype.encode(), 0, count,
                       status).ljust(BS, b'\0')


def wrap(src, dst):
    vol_blocks = os.path.getsize(src) // BS
    head = struct.pack('>2sHI', b'ER', BS, MAP_BLOCKS + vol_blocks).ljust(BS, b'\0')
    head += entry(1, MAP_BLOCKS - 1, 'Apple', 'Apple_partition_map', 0x3)
    head += entry(MAP_BLOCKS, vol_blocks, 'Mac_OS_X', 'Apple_HFS', 0x7F)
    with open(dst, 'wb') as out, open(src, 'rb') as inp:
        out.write(head.ljust(MAP_BLOCKS * BS, b'\0'))
        shutil.copyfileobj(inp, out, 16 << 20)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['check'] and len(a) == 2:
        sys.exit(0 if bare_hfs(a[1]) else 1)
    elif a[:1] == ['wrap'] and len(a) == 3:
        wrap(a[1], a[2])
    else:
        sys.exit(__doc__)
