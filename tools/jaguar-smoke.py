#!/usr/bin/env python3
"""Boot a Mac OS X 10.2 Jaguar disk on the emulated Radeon 9000 and check that
the desktop comes up and OpenGL works.

    tools/jaguar-smoke.py ~/Downloads/MacOSJaguar.img [--chess]

Boots the disk with `ppcosx --jaguar --snapshot --monitor` (nothing is
written to it), waits for the Aqua desktop, and with --chess opens Chess from
the Finder's Applications window, makes a move, and checks that the 3D board
was drawn.  Exits 0 on success; the screenshots (smoke-*.png) are left in
the current directory.

It sees what is on the screen, so it assumes the disk auto-logs in to a
Finder window with the Applications button at the top of the window, as the
MacOSJaguar.img this was written against does.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vmctl

REPO = os.path.dirname(HERE)


def pixels(ppm):
    """(width, height, rgb bytes) of a P6 screendump."""
    with open(ppm, 'rb') as f:
        data = f.read()
    parts = data.split(None, 4)         # P6 w h maxval <data>
    w, h = int(parts[1]), int(parts[2])
    return w, h, parts[4][-w * h * 3:]


def px(img, x, y):
    w, h, d = img
    i = (y * w + x) * 3
    return d[i], d[i + 1], d[i + 2]


def shot(name):
    """Screendump to smoke-NAME.png; returns the pixels."""
    ppm = os.path.abspath('smoke-%s.ppm' % name)
    if os.path.exists(ppm):
        os.remove(ppm)
    vmctl.hmp('screendump "%s"' % ppm, 0.5)
    for _ in range(40):
        if os.path.exists(ppm) and os.path.getsize(ppm) > 1000:
            time.sleep(0.2)
            break
        time.sleep(0.1)
    img = pixels(ppm)
    subprocess.run(['sips', '-s', 'format', 'png', ppm, '--out', ppm[:-4] + '.png'],
                   capture_output=True)
    os.remove(ppm)
    return img


def desktop_up(img):
    # Aqua menu bar: light across the top; blue desktop picture below it
    top = [px(img, x, 5) for x in range(200, 600, 40)]
    desk = px(img, 40, 400)
    return all(min(p) > 200 for p in top) and desk[2] > desk[0] + 40


def wait(cond, what, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        img = shot('wait')
        if cond(img):
            return img
        time.sleep(3)
    sys.exit('smoke: timed out waiting for ' + what)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    disk = os.path.abspath(sys.argv[1])
    chess = '--chess' in sys.argv
    vmdir = os.environ.get('PPCOSX_VM_DIR') or os.path.join(
        os.environ.get('TMPDIR', '/tmp'), 'jaguar-smoke-vm')
    os.makedirs(vmdir, exist_ok=True)
    env = dict(os.environ, PPCOSX_VM_DIR=vmdir)
    vm = subprocess.Popen([os.path.join(REPO, 'ppcosx'), '--jaguar', '--snapshot',
                           '--monitor', '--no-audio', '--disk', disk],
                          env=env, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    try:
        time.sleep(15)
        img = wait(desktop_up, 'the Aqua desktop', 150)
        print('desktop up')
        if chess:
            vmctl.click(626, 138)                  # Applications in the toolbar
            time.sleep(3)
            vmctl.click(444, 285, n=2)             # Chess
            # the board is wood-brown (R > G > B) at the left edge of the window
            def board(img):
                r, g, b = px(img, 60, 400)
                return r > g + 8 and g > b + 20 and r > 50
            wait(board, 'the Chess board', 90)
            print('chess drew its 3D board')
            time.sleep(5)
            before = shot('chess-before')
            vmctl.drag(394, 420, 392, 330)         # e2-e4
            time.sleep(8)
            after = shot('chess')
            # the pawn left e2 and came to e4: the board changed there
            changed = sum(px(before, x, y) != px(after, x, y)
                          for x in range(350, 430, 2) for y in range(300, 450, 2))
            print('pixels changed around e2-e4: %d' % changed)
            if changed < 300:
                sys.exit('smoke: the e2-e4 move did not show')
        print('PASS')
    finally:
        vmctl.hmp('quit', 0.2)
        try:
            vm.wait(10)
        except subprocess.TimeoutExpired:
            vm.kill()


main()
