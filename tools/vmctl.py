#!/usr/bin/env python3
"""Drive a running VM from the host (for scripting and testing).

Start the VM with `./ppcosx run --monitor`, then:

    tools/vmctl.py cmd '<HMP command>'     e.g. cmd 'info pci'
    tools/vmctl.py type 'text'             type into the guest
    tools/vmctl.py key cmd-q               one key combo (HMP sendkey syntax)
    tools/vmctl.py shot out.png            screenshot
    tools/vmctl.py click X Y [right]       click / dclick / move / drag x0 y0 x1 y1

Coordinates are guest pixels at 1024x768.
"""
import socket, sys, time, json, os, subprocess

def hmp(cmd, wait=0.3):
    s = socket.create_connection(('127.0.0.1', 4444))
    s.settimeout(2)
    buf = b''
    try:
        while b'(qemu)' not in buf:
            buf += s.recv(4096)
    except socket.timeout:
        pass
    s.sendall(cmd.encode() + b'\n')
    time.sleep(wait)
    out = b''
    try:
        while True:
            d = s.recv(65536)
            if not d:
                break
            out += d
            if out.rstrip().endswith(b'(qemu)'):
                break
    except socket.timeout:
        pass
    s.close()
    return out.decode(errors='replace')

KEYS = {' ': 'spc', '\n': 'ret', '\t': 'tab', '-': 'minus', '=': 'equal',
        '[': 'bracket_left', ']': 'bracket_right', '\\': 'backslash',
        ';': 'semicolon', "'": 'apostrophe', '`': 'grave_accent', ',': 'comma',
        '.': 'dot', '/': 'slash'}
SHIFTED = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7',
           '*': '8', '(': '9', ')': '0', '_': 'minus', '+': 'equal', '{': 'bracket_left',
           '}': 'bracket_right', '|': 'backslash', ':': 'semicolon', '"': 'apostrophe',
           '~': 'grave_accent', '<': 'comma', '>': 'dot', '?': 'slash'}

def keyname(c):
    if c.isalpha():
        return ('shift-' if c.isupper() else '') + c.lower()
    if c.isdigit():
        return c
    if c in KEYS:
        return KEYS[c]
    if c in SHIFTED:
        k = SHIFTED[c]
        return 'shift-' + KEYS.get(k, k)
    raise ValueError(c)

def qmp(cmds):
    s = socket.create_connection(('127.0.0.1', 4445))
    f = s.makefile('rw')
    f.readline()
    f.write(json.dumps({'execute': 'qmp_capabilities'}) + '\n'); f.flush(); f.readline()
    res = []
    for c in cmds:
        f.write(json.dumps(c) + '\n'); f.flush()
        while True:
            l = json.loads(f.readline())
            if 'return' in l or 'error' in l:
                res.append(l); break
    s.close()
    return res

W, H = 1024, 768
SCALE = 1.1775      # Tiger's HID stack scales tablet input about the centre
def absev(x, y):
    x = (x - W / 2) / SCALE + W / 2
    y = (y - H / 2) / SCALE + H / 2
    x = min(max(x, 0), W - 1); y = min(max(y, 0), H - 1)
    return {'execute': 'input-send-event', 'arguments': {'events': [
        {'type': 'abs', 'data': {'axis': 'x', 'value': int(x * 32767 / (W - 1))}},
        {'type': 'abs', 'data': {'axis': 'y', 'value': int(y * 32767 / (H - 1))}}]}}
def btn(down, b='left'):
    return {'execute': 'input-send-event', 'arguments': {'events': [
        {'type': 'btn', 'data': {'down': down, 'button': b}}]}}

def move(x, y):
    qmp([absev(x, y)])
def click(x, y, b='left', n=1):
    qmp([absev(x, y)]); time.sleep(0.15)
    for i in range(n):
        qmp([btn(True, b)]); time.sleep(0.08); qmp([btn(False, b)]); time.sleep(0.08)
def drag(x0, y0, x1, y1, steps=20):
    qmp([absev(x0, y0)]); time.sleep(0.2); qmp([btn(True)]); time.sleep(0.2)
    for i in range(1, steps + 1):
        qmp([absev(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)]); time.sleep(0.05)
    time.sleep(0.2); qmp([btn(False)])

def typ(text, delay=0.03):
    s = socket.create_connection(('127.0.0.1', 4444))
    s.settimeout(0.5)
    try:
        s.recv(4096)
    except socket.timeout:
        pass
    for c in text:
        s.sendall(('sendkey %s\n' % keyname(c)).encode())
        time.sleep(delay)
    time.sleep(0.3)
    s.close()

def shot(path):
    tmp = path + '.ppm'
    hmp('screendump "%s"' % os.path.abspath(tmp), 1.5)
    subprocess.run(['sips', '-s', 'format', 'png', tmp, '--out', path],
                   capture_output=True)
    os.remove(tmp)

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'cmd': print(hmp(a[1], float(a[2]) if len(a) > 2 else 0.5))
    elif a[0] == 'type': typ(a[1])
    elif a[0] == 'key': hmp('sendkey ' + a[1])
    elif a[0] == 'shot': shot(a[1])
    elif a[0] == 'click': click(float(a[1]), float(a[2]), a[3] if len(a) > 3 else 'left')
    elif a[0] == 'dclick': click(float(a[1]), float(a[2]), n=2)
    elif a[0] == 'move': move(float(a[1]), float(a[2]))
    elif a[0] == 'drag': drag(*map(float, a[1:5]))
