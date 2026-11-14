#!/usr/bin/env python3
"""Reset the ESP32 (EN via RTS, IO0 left high) and print its serial log for N seconds. Stdlib only."""
import fcntl, os, struct, sys, termios, time

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 12
reset = "--no-reset" not in sys.argv

fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
a = termios.tcgetattr(fd)
a[0] = 0; a[1] = 0; a[3] = 0
a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
a[4] = a[5] = termios.B115200
a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 1
termios.tcsetattr(fd, termios.TCSANOW, a)

def line(bit, on):
    fcntl.ioctl(fd, termios.TIOCMBIS if on else termios.TIOCMBIC, struct.pack("I", bit))

# Opening the port asserts DTR+RTS (no effect on the auto-reset circuit). Release RTS first:
# RTS alone would pull EN low and reset the chip; DTR alone only touches IO0, which is
# ignored while the chip is running.
line(termios.TIOCM_RTS, False)          # EN high
line(termios.TIOCM_DTR, False)          # IO0 high: normal boot
if reset:
    line(termios.TIOCM_RTS, True)       # EN low
    time.sleep(0.1)
    line(termios.TIOCM_RTS, False)      # EN high: run
termios.tcflush(fd, termios.TCIFLUSH)

end = time.time() + secs
buf = b""
while time.time() < end:
    d = os.read(fd, 4096)
    if d:
        buf += d
        *lines, buf = buf.split(b"\n")
        for l in lines:
            # strip ANSI colour codes from ESP_LOG
            s = l.decode(errors="replace").rstrip("\r")
            while "\x1b[" in s:
                i = s.index("\x1b["); j = s.find("m", i)
                s = s[:i] + s[j + 1:] if j > 0 else s[:i]
            print(s, flush=True)
if buf:
    print(buf.decode(errors="replace"))
os.close(fd)
