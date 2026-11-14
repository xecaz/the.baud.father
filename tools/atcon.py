#!/usr/bin/env python3
"""Talk to the ESP32's AT console (firmware console.c) over USB. Stdlib only.

Interactive:   python3 -I tools/atcon.py /dev/ttyUSB0 [--log FILE]
               type :d / :a to pick a modem, then AT commands; Ctrl+D or Ctrl+C quits.
Scripted:      python3 -I tools/atcon.py /dev/ttyUSB0 --cmd ":d" --cmd "ATI4" --cmd ":off" [--wait 2] [--log FILE]
               sends each --cmd, waits --wait seconds (default 2) for replies after each, then exits.
The board is not reset (use --reset to restart it first). Only one program may have the port open.

Straight to a modem (USB-RS232 adapter, no ESP32):  --modem [--baud 9600]
               raises DTR and RTS (the Courier ignores AT with DTR off) and talks at --baud (default 9600).
"""
import fcntl, os, select, struct, sys, termios, time

args = sys.argv[1:]
port = args.pop(0) if args and not args[0].startswith("--") else "/dev/ttyUSB0"
cmds, wait, logf, reset, modem, baud = [], 2.0, None, False, False, None
while args:
    a = args.pop(0)
    if a == "--cmd": cmds.append(args.pop(0))
    elif a == "--wait": wait = float(args.pop(0))
    elif a == "--log": logf = open(args.pop(0), "a")
    elif a == "--reset": reset = True
    elif a == "--modem": modem = True
    elif a == "--baud": baud = int(args.pop(0))
    else: sys.exit(f"unknown argument {a}\n" + __doc__)

fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
t = termios.tcgetattr(fd)
t[0] = 0; t[1] = 0; t[3] = 0
t[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
if baud is None:
    baud = 9600 if modem else 115200
t[4] = t[5] = getattr(termios, f"B{baud}")
t[6][termios.VMIN] = 0; t[6][termios.VTIME] = 0
termios.tcsetattr(fd, termios.TCSANOW, t)

def line(bit, on):
    fcntl.ioctl(fd, termios.TIOCMBIS if on else termios.TIOCMBIC, struct.pack("I", bit))

if modem:
    line(termios.TIOCM_DTR, True)   # DTR on: the modem accepts commands
    line(termios.TIOCM_RTS, True)   # RTS on: the modem may send (in case &R2 is stored)
else:
    line(termios.TIOCM_RTS, False)  # EN high (RTS alone would reset the chip)
    line(termios.TIOCM_DTR, False)  # IO0 high
if reset and not modem:
    line(termios.TIOCM_RTS, True); time.sleep(0.1); line(termios.TIOCM_RTS, False)

def show(data):
    s = data.decode(errors="replace").replace("\r", "")
    while "\x1b[" in s:                         # strip ESP_LOG colour codes
        i = s.index("\x1b["); j = s.find("m", i)
        s = s[:i] + s[j + 1:] if j > 0 else s[:i]
    sys.stdout.write(s); sys.stdout.flush()
    if logf: logf.write(s); logf.flush()

def pump(secs):
    end = time.time() + secs
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            d = os.read(fd, 4096)
            if d: show(d)

def send(text):
    if logf: logf.write(f">>> {text}\n"); logf.flush()
    os.write(fd, text.encode() + b"\r")

try:
    if reset:
        pump(10)                                # boot + modem probe (~9 s) before the console starts
    if cmds:
        pump(0.3)
        for c in cmds:
            print(f">>> {c}", flush=True)
            send(c)
            pump(wait)
    else:
        print("# connected (Ctrl+D / Ctrl+C quits); :help lists the commands", flush=True)
        while True:
            r, _, _ = select.select([fd, sys.stdin], [], [])
            if fd in r:
                d = os.read(fd, 4096)
                if d: show(d)
            if sys.stdin in r:
                l = sys.stdin.readline()
                if not l: break
                send(l.rstrip("\r\n"))
except KeyboardInterrupt:
    pass
finally:
    os.close(fd)
    if logf: logf.close()
