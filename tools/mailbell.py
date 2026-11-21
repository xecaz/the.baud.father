#!/usr/bin/env python3
"""Ring the Baudfather from the laptop when a desktop notification from a chosen program appears
(Thunderbird: "Incoming e-mail" in the robot voice).

Stdlib only; uses the system's dbus-monitor (session bus) and bluetoothctl (BlueZ). The laptop must be paired
with the box once (hold RING 3-9 s, then `bluetoothctl --agent NoInputNoOutput`, `scan le`, `pair <addr>`).

    python3 -I tools/mailbell.py                 # watch, ring ringtone 5 for Thunderbird
    python3 -I tools/mailbell.py --test          # ring once now and exit
    python3 -I tools/mailbell.py --app thunderbird=5 --app signal=3 --min-gap 60
    python3 -I tools/mailbell.py --show          # print the program name of every notification (to find names)

Only the notification's program name is read; titles and texts are never looked at or logged.
One ring per program per --min-gap seconds (bursts of mail ring once). GATT contract: notes/ble.md.
"""
import argparse
import re
import subprocess
import sys
import time

BOX_NAME = "doorbell"                                       # the box's Bluetooth name; its address is looked up
TRIGGER = "2139d582-b04a-4808-8e1f-f08bb13d8de6"            # trigger characteristic
TONE_BASE = 0x10                                            # 0x10 + n = ringtone n
MATCH = "type='method_call',interface='org.freedesktop.Notifications',member='Notify'"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def find_box(name=BOX_NAME):
    """Address of the paired device with this name (from `bluetoothctl devices`), or None."""
    out = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, timeout=10).stdout
    for line in out.splitlines():
        m = re.match(r"Device ([0-9A-Fa-f:]{17}) (.+)$", line.strip())
        if m and m.group(2).strip() == name:
            return m.group(1)
    return None


def ring(tone, box):
    """Ringtone n. True if the write was attempted on a connected link."""
    return write([TONE_BASE + tone], box)


def write(data, box):
    """Connect, write these bytes to the trigger in one go, disconnect. True if the write was attempted on a connected link."""
    value = " ".join(f"0x{b:02x}" for b in data)
    steps = ((f"connect {box}", 7), (f"gatt.select-attribute {TRIGGER}", 1), (f'gatt.write "{value}"', 2),
             (f"disconnect {box}", 2), ("quit", 0))
    p = subprocess.Popen(["bluetoothctl"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for cmd, wait in steps:
            p.stdin.write(cmd + "\n")
            p.stdin.flush()
            time.sleep(wait)
        out, _ = p.communicate(timeout=10)
    except (BrokenPipeError, subprocess.TimeoutExpired):
        p.kill()
        return False
    return "Connection successful" in out and "Attempting to write" in out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", action="append", metavar="NAME=N",
                    help="program name (substring, any case) = ringtone number; repeatable (default thunderbird=5)")
    ap.add_argument("--min-gap", type=int, default=60, help="seconds between rings for one program (default 60)")
    ap.add_argument("--box", help="the box's BLE address (default: the paired device named \"%s\")" % BOX_NAME)
    ap.add_argument("--test", action="store_true", help="ring the first mapping once and exit")
    ap.add_argument("--show", action="store_true", help="print every notification's program name, ring nothing")
    a = ap.parse_args()
    a.box = a.box or find_box()
    if not a.box:
        sys.exit(f"no paired Bluetooth device named {BOX_NAME!r}: pair the laptop with the box first, or pass --box")
    apps = {}
    for spec in a.app or ["thunderbird=5"]:
        name, _, n = spec.partition("=")
        if not n.isdigit():
            sys.exit(f"expected NAME=N, got {spec!r}")
        apps[name.lower()] = int(n)

    if a.test:
        name, tone = next(iter(apps.items()))
        ok = ring(tone, a.box)
        log(f"test ring, ringtone {tone}: {'sent' if ok else 'FAILED (box out of range, busy, or not paired)'}")
        sys.exit(0 if ok else 1)

    mon = subprocess.Popen(["dbus-monitor", "--session", MATCH], stdout=subprocess.PIPE, text=True, bufsize=1)
    log("watching notifications for: " + ", ".join(f"{k} -> ringtone {v}" for k, v in apps.items()))
    last = {}
    expect_name = False
    for line in mon.stdout:
        if line.startswith("method call") and "member=Notify" in line:
            expect_name = True                               # the first argument (next line) is the program name
            continue
        if not expect_name:
            continue
        expect_name = False
        m = re.match(r'\s+string "(.*)"', line)
        if not m:
            continue
        prog = m.group(1)
        if a.show:
            log(f"notification from {prog!r}")
            continue
        for key, tone in apps.items():
            if key in prog.lower():
                now = time.time()
                if now - last.get(key, 0) < a.min_gap:
                    log(f"{prog}: skipped (rang {int(now - last[key])} s ago)")
                else:
                    last[key] = now
                    ok = ring(tone, a.box)
                    log(f"{prog}: ringtone {tone} {'sent' if ok else 'FAILED'}")
                break
    sys.exit("dbus-monitor ended")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
