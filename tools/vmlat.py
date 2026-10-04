#!/usr/bin/env python3
"""Desktop latency of a running VM: input -> first visible change -> settled.

Start the VM with `./ppcosx run --monitor`, wait for the desktop, then:

    tools/vmlat.py folder [N]     double-click Macintosh HD, close the window (Cmd-W)
    tools/vmlat.py dashboard [N]  F12 in, F12 out

Each input waits for the previous transition to settle.  The screen is
compared below the menu bar (its clock changes).  "first" is the first
screendump that differs from the one before the input, "settled" the last
change before SETTLE seconds without one (or the timeout).  Times are in
seconds and as fine as one screendump (about 20-50 ms).  Results go to stdout
as one line per transition and a median per kind.
"""
import hashlib, os, socket, statistics, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vmctl  # noqa: E402

SETTLE = float(os.environ.get('VMLAT_SETTLE', '1.0'))
TIMEOUT = float(os.environ.get('VMLAT_TIMEOUT', '20'))
TMP = '/tmp/vmlat-%d.ppm' % os.getpid()
MENU_ROWS = 22


class Monitor:
    """One HMP connection kept open: a screendump per call, no reconnects."""

    def __init__(self):
        self.s = socket.create_connection(('127.0.0.1', 4444))
        self.s.settimeout(5)
        self.read_prompt()

    def read_prompt(self):
        buf = b''
        while not buf.endswith(b'(qemu) '):
            buf += self.s.recv(4096)

    def cmd(self, line):
        self.s.sendall((line + '\n').encode())
        self.read_prompt()

    def screen(self):
        """Hash of the screen below the menu bar."""
        self.s.sendall(('screendump %s\n' % TMP).encode())
        self.read_prompt()
        w, h, rgb = vmctl.read_ppm(TMP, 5)
        vmctl.SIZE = (w, h)         # so clicks don't take a screendump of their own
        return hashlib.md5(rgb[MENU_ROWS * w * 3:]).digest()


def transition(mon, act):
    """Do act(); return (first change, settled) in seconds, None if no change."""
    before = mon.screen()
    t0 = time.monotonic()
    act()
    first = last = None
    prev = before
    while True:
        cur = mon.screen()
        now = time.monotonic()
        if cur != prev:
            if first is None:
                first = now - t0
            last = now - t0
            prev = cur
        if (last is not None and now - t0 - last >= SETTLE) or now - t0 >= TIMEOUT:
            return first, last


def main():
    kind = sys.argv[1] if len(sys.argv) > 1 else ''
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    mon = Monitor()
    if kind == 'folder':
        # the Macintosh HD icon (VMLAT_HD=x,y if the desktop differs)
        x, y = map(int, os.environ.get('VMLAT_HD', '945,60').split(','))
        steps = [('open', lambda: vmctl.click(x, y, n=2)),
                 ('close', lambda: mon.cmd('sendkey meta_l-w'))]
    elif kind == 'dashboard':
        steps = [('in', lambda: mon.cmd('sendkey f12')),
                 ('out', lambda: mon.cmd('sendkey f12'))]
    else:
        sys.exit(__doc__)
    res = {name: [] for name, _ in steps}
    for i in range(n):
        for name, act in steps:
            first, settled = transition(mon, act)
            res[name].append(settled if settled is not None else TIMEOUT)
            print('%s %s %d: first %s, settled %s' % (kind, name, i + 1,
                  '%.2f' % first if first is not None else '-',
                  '%.2f' % settled if settled is not None else 'timeout'), flush=True)
    for name, v in res.items():
        print('%s %s median settled %.2f s (n=%d)' % (kind, name, statistics.median(v), len(v)))
    if os.path.exists(TMP):
        os.remove(TMP)


if __name__ == '__main__':
    main()
