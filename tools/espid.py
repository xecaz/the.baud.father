#!/usr/bin/env python3
"""Read-only ESP32 chip identification via the ROM bootloader (stdlib only).
Resets into download mode with DTR/RTS, SYNCs, reads registers with READ_REG.
Writes nothing to flash or eFuse. Then resets the chip back to normal boot."""
import fcntl, os, struct, sys, termios, time

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
fd = os.open(PORT, os.O_RDWR | os.O_NOCTTY)
a = termios.tcgetattr(fd)
a[0] = 0; a[1] = 0; a[3] = 0
a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
a[4] = a[5] = termios.B115200
a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 1
termios.tcsetattr(fd, termios.TCSANOW, a)

def line(bit, on):
    fcntl.ioctl(fd, termios.TIOCMBIS if on else termios.TIOCMBIC, struct.pack("I", bit))
DTR, RTS = termios.TIOCM_DTR, termios.TIOCM_RTS

def reset(bootloader):
    line(DTR, False); line(RTS, True)          # EN low
    time.sleep(0.1)
    if bootloader:
        line(DTR, True); line(RTS, False)      # IO0 low, EN high
        time.sleep(0.05)
        line(DTR, False)
    else:
        line(RTS, False)

def slip(b):
    return b"\xc0" + b.replace(b"\xdb", b"\xdb\xdd").replace(b"\xc0", b"\xdb\xdc") + b"\xc0"

buf = b""
def read_frame(timeout=1.0):
    global buf
    end = time.time() + timeout
    while time.time() < end:
        s = buf.find(b"\xc0")
        if s >= 0:
            e = buf.find(b"\xc0", s + 1)
            if e > s:
                f = buf[s + 1:e]; buf = buf[e:]
                if not f:
                    continue
                return f.replace(b"\xdb\xdc", b"\xc0").replace(b"\xdb\xdd", b"\xdb")
        d = os.read(fd, 4096)
        if d:
            buf += d
    return None

def cmd(op, data=b"", timeout=1.0):
    os.write(fd, slip(struct.pack("<BBHI", 0, op, len(data), 0) + data))
    end = time.time() + timeout
    while time.time() < end:
        f = read_frame(end - time.time())
        if f and len(f) >= 8 and f[0] == 1 and f[1] == op:
            return struct.unpack("<I", f[4:8])[0], f[8:]
    return None

ok = False
for attempt in range(5):
    reset(True); time.sleep(0.2)
    termios.tcflush(fd, termios.TCIFLUSH); buf = b""
    for _ in range(5):
        if cmd(0x08, b"\x07\x07\x12\x20" + b"\x55" * 32, 0.3):
            ok = True; break
    if ok:
        break
if not ok:
    print("no SYNC: hold BOOT while it resets, or check the cable"); sys.exit(1)
time.sleep(0.1); termios.tcflush(fd, termios.TCIFLUSH); buf = b""

def reg(addr):
    r = cmd(0x0A, struct.pack("<I", addr))
    if r is None:
        raise SystemExit(f"READ_REG {addr:#x} failed")
    return r[0]

magic = reg(0x40001000)
print(f"chip magic: {magic:#010x}", "(ESP32)" if magic == 0x00F01D83 else "(NOT original ESP32)")
if magic == 0x00F01D83:
    E = 0x3FF5A000
    w = [reg(E + 4 * i) for i in range(7)]
    mac = struct.pack(">II", w[2], w[1])[2:]
    pkg = ((w[3] >> 9) & 7) | (((w[3] >> 2) & 1) << 3)
    pkgs = {0: "ESP32-D0WDQ6", 1: "ESP32-D0WD(Q5)", 2: "ESP32-D2WD (embedded flash)",
            4: "ESP32-U4WDH", 5: "ESP32-PICO-D4", 6: "ESP32-PICO-V3-02", 7: "ESP32-D0WDR2-V3"}
    rev = 0
    if (w[3] >> 15) & 1:
        rev = 1
        if (w[5] >> 20) & 1:
            rev = 2
            if (reg(0x3FF6607C) >> 31) & 1:
                rev = 3
    print("package:", pkgs.get(pkg, f"unknown ({pkg})"))
    print("major revision:", rev, "(V3 = ECO3)" if rev == 3 else "")
    print("cores:", 1 if w[3] & 1 else 2, "| BT:", "DISABLED in eFuse" if w[3] & 2 else "enabled")
    print("MAC:", ":".join(f"{b:02x}" for b in mac))
reset(False)
os.close(fd)
