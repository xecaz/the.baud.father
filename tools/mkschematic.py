#!/usr/bin/env python3
"""Full schematic of the doorbell box (notes/schematic.svg). Stdlib only.
Every part, pin and connection as built 2026-11-14. Main-board hole names (e.g. L2, B20) are from
notes/mainboard.png, line-board holes (e.g. C2, G3) from notes/lineboard.png.
Render: rsvg-convert -b white -o notes/schematic.png notes/schematic.svg"""
import os

S = []          # svg elements
FS = 12         # base font size
DOTS = []

def t(x, y, s, size=FS, anchor="start", weight="normal", fill="#111", italic=False):
    st = ' font-style="italic"' if italic else ""
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}"{st}>{s}</text>')

def w(*pts, col="#111", width=1.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    p = " ".join(f"{x},{y}" for x, y in pts)
    S.append(f'<polyline points="{p}" fill="none" stroke="{col}" stroke-width="{width}"{d}/>')

def dot(x, y): DOTS.append((x, y))

def box(x, y, bw, bh, title, sub=None, fill="#f6f6f6", stroke="#333", title_in=True):
    S.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    if title:
        t(x + bw / 2, y + 16, title, FS + 1, "middle", "bold")
    if sub:
        for i, line in enumerate(sub if isinstance(sub, list) else [sub]):
            t(x + bw / 2, y + 31 + i * 14, line, FS - 2, "middle", fill="#444")

def frame(x, y, fw, fh, title, col):
    S.append(f'<rect x="{x}" y="{y}" width="{fw}" height="{fh}" rx="8" fill="none" stroke="{col}" stroke-width="2" stroke-dasharray="8,5"/>')
    t(x + 10, y + 18, title, FS + 2, weight="bold", fill=col)

def pin(x, y, side, label, num=None, stub=14):
    """pin on a box edge at (x, y); side 'l' or 'r'. Returns the outer end of the stub."""
    if side == "l":
        w((x - stub, y), (x, y))
        t(x + 5, y + 4, label, FS - 1)
        if num is not None: t(x - stub + 2, y - 4, str(num), FS - 3, fill="#666")
        return (x - stub, y)
    w((x, y), (x + stub, y))
    t(x - 5, y + 4, label, FS - 1, "end")
    if num is not None: t(x + stub - 2, y - 4, str(num), FS - 3, "end", fill="#666")
    return (x + stub, y)

def gnd(x, y):
    w((x, y), (x, y + 8))
    for i, hw in enumerate((9, 6, 3)):
        w((x - hw, y + 8 + i * 4), (x + hw, y + 8 + i * 4), width=1.8)

def flag(x, y, name, side="r", col="#8e44ad"):
    """net label flag; side = direction the flag points from the wire end"""
    wd = 7.2 * len(name) + 12
    if side == "r":
        pts = [(x, y), (x + 8, y - 9), (x + wd, y - 9), (x + wd, y + 9), (x + 8, y + 9)]
        tx = x + 8 + (wd - 8) / 2
    else:
        pts = [(x, y), (x - 8, y - 9), (x - wd, y - 9), (x - wd, y + 9), (x - 8, y + 9)]
        tx = x - 8 - (wd - 8) / 2
    p = " ".join(f"{a},{b}" for a, b in pts)
    S.append(f'<polygon points="{p}" fill="#fff" stroke="{col}" stroke-width="1.4"/>')
    t(tx, y + 4, name, FS - 1, "middle", "bold", col)

def res(x1, y, x2, label, vertical=False):
    """resistor between (x1,y) and (x2,y) horizontally, or (x,y1)-(x,y2) vertically if vertical (x1=x, y=y1, x2=y2)"""
    if not vertical:
        m = (x1 + x2) / 2
        w((x1, y), (m - 18, y)); w((m + 18, y), (x2, y))
        S.append(f'<rect x="{m-18}" y="{y-6}" width="36" height="12" fill="#fff" stroke="#111" stroke-width="1.6"/>')
        t(m, y - 10, label, FS - 1, "middle")
    else:
        x, ya, yb = x1, y, x2
        m = (ya + yb) / 2
        w((x, ya), (x, m - 18)); w((x, m + 18), (x, yb))
        S.append(f'<rect x="{x-6}" y="{m-18}" width="12" height="36" fill="#fff" stroke="#111" stroke-width="1.6"/>')
        t(x + 10, m + 4, label, FS - 1)

def cap(x1, y, x2, label, polar=False, vertical=False, plus_first=True):
    if not vertical:
        m = (x1 + x2) / 2
        w((x1, y), (m - 4, y)); w((m + 4, y), (x2, y))
        w((m - 4, y - 10), (m - 4, y + 10), width=2.2)
        if polar:
            S.append(f'<path d="M {m+7} {y-10} Q {m+3} {y} {m+7} {y+10}" fill="none" stroke="#111" stroke-width="2.2"/>')
            t(m - 10 if plus_first else m + 12, y - 12, "+", FS, "middle", "bold")
        else:
            w((m + 4, y - 10), (m + 4, y + 10), width=2.2)
        t(m, y + 24, label, FS - 1, "middle")
    else:
        x, ya, yb = x1, y, x2
        m = (ya + yb) / 2
        w((x, ya), (x, m - 4)); w((x, m + 4), (x, yb))
        w((x - 10, m - 4), (x + 10, m - 4), width=2.2)
        if polar:
            S.append(f'<path d="M {x-10} {m+7} Q {x} {m+3} {x+10} {m+7}" fill="none" stroke="#111" stroke-width="2.2"/>')
            t(x - 14, m - 6, "+", FS, "middle", "bold")
        else:
            w((x - 10, m + 4), (x + 10, m + 4), width=2.2)
        t(x + 14, m + 4, label, FS - 1)

def diode(x1, y, x2, label, left=False):
    m = (x1 + x2) / 2
    w((x1, y), (m - 8, y)); w((m + 8, y), (x2, y))
    k = -1 if left else 1
    S.append(f'<polygon points="{m-8*k},{y-8} {m-8*k},{y+8} {m+8*k},{y}" fill="#fff" stroke="#111" stroke-width="1.6"/>')
    w((m + 8 * k, y - 8), (m + 8 * k, y + 8), width=2.2)
    t(m, y - 13, label, FS - 1, "middle")

def switch(x1, y, x2, label, push=False):
    m = (x1 + x2) / 2
    w((x1, y), (m - 14, y)); w((m + 14, y), (x2, y))
    S.append(f'<circle cx="{m-14}" cy="{y}" r="2.5" fill="#fff" stroke="#111"/>')
    S.append(f'<circle cx="{m+14}" cy="{y}" r="2.5" fill="#fff" stroke="#111"/>')
    if push:
        w((m - 16, y - 8), (m + 16, y - 8), width=2); w((m, y - 8), (m, y - 16), width=2)
    else:
        w((m - 12, y - 1), (m + 13, y - 11), width=2)
    t(m, y - 20, label, FS - 1, "middle")

def fuse(x1, y, x2, label):
    m = (x1 + x2) / 2
    w((x1, y), (m - 16, y)); w((m + 16, y), (x2, y))
    S.append(f'<rect x="{m-16}" y="{y-6}" width="32" height="12" fill="#fff" stroke="#111" stroke-width="1.6"/>')
    w((m - 16, y), (m + 16, y), width=1)
    t(m, y - 11, label, FS - 1, "middle")

def led(x1, y, x2, label):
    diode(x1, y, x2, "", left=True)
    t((x1 + x2) / 2, y - 26, label, FS - 1, "middle")
    m = (x1 + x2) / 2
    for dx in (0, 7):
        w((m + dx - 2, y - 12), (m + dx + 6, y - 20), width=1.2)

# ---------------------------------------------------------------- title
t(30, 34, "modem.doorbell: full schematic (as built 2026-11-14)", 22, weight="bold")
t(30, 56, "Main-board holes in [brackets] (notes/mainboard.png), line-board holes in {braces} (notes/lineboard.png). "
  "Couriers' LINE jacks never go on a real phone line.", FS, fill="#444")

# ---------------------------------------------------------------- power chain
frame(20, 80, 690, 190, "Panel power (back wall)", "#8e44ad")
YP, YN = 150, 220
box(36, 120, 86, 120, "J0 barrel")
t(79, 190, "5.5/2.1", FS - 3, "middle", fill="#555")
pin(122, YP, "r", "centre", stub=0); pin(122, YN, "r", "sleeve", stub=0)
fuse(122, YP, 232, "F1 T500 mA 5×20")
diode(232, YP, 322, "D1 1N5819")
t(277, YP + 24, "band → switch", FS - 2, "middle", fill="#555")
switch(322, YP, 420, "SW1 rocker")
w((420, YP), (470, YP)); dot(450, YP)
t(405, YP + 22, "+12 V rail", FS - 1, "middle", "bold", "#8e44ad")
box(470, 115, 130, 135, "U1 LM2596")
for i, l in enumerate(["buck 12→5 V", "set to 5.0 V", "IN− = OUT−"]): t(535, 176 + i * 13, l, FS - 3, "middle", fill="#555")
pin(470, YP, "l", "IN+", stub=0); pin(470, YN, "l", "IN−", stub=0)
pin(600, YP, "r", "OUT+", stub=0); pin(600, YN, "r", "OUT−", stub=0)
w((122, YN), (470, YN))
t(300, YN - 6, "GND (sleeve)", FS - 1, "middle", fill="#555")
t(36, 262, "12 V adapter 12.3 V, 2.5 A, centre +", FS - 2, fill="#555")

# J4 harness into the main board
J4X, J4Y = 690, 330
box(J4X, J4Y - 30, 64, 150, "J4", None)
t(J4X + 32, J4Y + 134, "[P30–S30]", FS - 3, "middle", fill="#555")
ys4 = [J4Y, J4Y + 28, J4Y + 56, J4Y + 84]
for i, (yy, lab) in enumerate(zip(ys4, ["+12V", "GND", "+5V", "GND"])):
    pin(J4X, yy, "l", str(i + 1), stub=0)
    t(J4X + 60, yy + 4, lab, FS - 3, "end", fill="#555")
# rail -> J4.1
w((450, YP), (450, 280), (660, 280), (660, ys4[0]), (J4X, ys4[0]))
# OUT+ -> J4.3
w((600, YP), (640, YP), (640, ys4[2]), (J4X, ys4[2]))
# OUT- -> J4.2 and J4.4
w((600, YN), (620, YN), (620, ys4[1]), (J4X, ys4[1])); dot(620, ys4[1])
w((620, ys4[1]), (620, ys4[3]), (J4X, ys4[3]))


# ---------------------------------------------------------------- main board frame
frame(250, 290, 1065, 580, "Main board (perfboard 26 × 31)", "#1b7f3b")

# ESP32
EX, EY, EW, EH = 870, 320, 230, 530
box(EX, EY, EW, EH, "ESP32 DevKitC (WROOM-32)", None, fill="#eef3ff")
for i, l in enumerate(["AZ-Delivery 38-pin, CP2102", "micro USB = UART0 (logs, flash)", "onboard BOOT (GPIO0) = trigger",
                       "EN = reset, red LED = power", "flash pins D0–D3/CMD/CLK: never use"]):
    t(280, 790 + i * 14, ("ESP32: " if i == 0 else "") + l, FS - 2, fill="#444")
# J4 right side -> ESP
for yy in ys4: w((J4X + 64, yy), (J4X + 74, yy))
flag(J4X + 74, ys4[0], "+12V")
for yy in (ys4[1], ys4[3]): flag(J4X + 74, yy, "GND", col="#333")
w((J4X + 64, ys4[2]), (EX - 14, ys4[2])); pin(EX, ys4[2], "l", "5V [L2]")
t(810, ys4[2] - 6, "+5V", FS - 1, "middle", "bold", "#e67e22")

# 3V3 + C1
Y33 = 470
pin(EX, Y33, "l", "3V3 [L20]")
w((EX - 14, Y33), (780, Y33)); dot(800, Y33)
cap(800, Y33, 540, "C1 470 µF", polar=True, vertical=True)
t(814, 520, "[O20+ O21−]", FS - 3, fill="#555")
gnd(800, 540)
flag(780, Y33, "+3V3", side="l", col="#c0392b")
YG = 552
pin(EX, YG, "l", "GND [B14 B20 L7]")
w((EX - 14, YG), (850, YG)); gnd(850, YG)

# LED
YL = 610
pin(EX, YL, "l", "GPIO2 [B6]")
res(EX - 14, YL, 760, "R1 330 Ω")
t(813, YL + 22, "[X24–X28]", FS - 3, "middle", fill="#555")
box(712, YL - 22, 48, 72, "J5", None); t(736, YL + 62, "[X30 Y30]", FS - 3, "middle", fill="#555")
pin(760, YL, "r", "1", stub=0); pin(760, YL + 30, "r", "2", stub=0)
w((712, YL), (690, YL)); w((712, YL + 30), (690, YL + 30))
led(560, YL, 690, "LED green, panel (Ø6.5)")
w((560, YL), (540, YL), (540, YL + 30), (690, YL + 30))
gnd(620, YL + 30)
t(625, YL - 44, "LED+ → J5.1, LED− → J5.2 = GND", FS - 2, "middle", fill="#555")

# RING
YR = 700
pin(EX, YR, "l", "GPIO4 [B8] (pull-up)")
w((EX - 14, YR), (760, YR))
box(712, YR - 22, 48, 72, "J6", None); t(736, YR + 62, "[U30 V30]", FS - 3, "middle", fill="#555")
pin(760, YR, "r", "1", stub=0); pin(760, YR + 30, "r", "2", stub=0)
w((712, YR), (690, YR)); w((712, YR + 30), (690, YR + 30))
switch(560, YR, 690, "SW2 RING pushbutton (panel)", push=True)
w((560, YR), (540, YR), (540, YR + 30), (690, YR + 30)); gnd(620, YR + 30)
t(EX + 8, YR + 18, "active low", FS - 3, fill="#555")

# ---------------------------------------------------------------- dialer / answerer chains
def chain(y0, name, gp, holes, jname, jholes, cname, courier, power, extra):
    ys = [y0 + i * 28 for i in range(6)]       # J pins 1..6
    # ESP pins (TX RX DTR DCD) on ys[2..5]
    sig = ["TX", "RX", "DTR", "DCD"]
    for i in range(4):
        pin(EX + EW, ys[i + 2], "r", f"GPIO{gp[i]} [{holes[i]}]")
    JX = 1160
    box(JX, ys[0] - 24, 48, 6 * 28 + 20, jname, None)
    t(JX + 24, ys[5] + 30, jholes, FS - 3, "middle", fill="#555")
    for i, yy in enumerate(ys):
        pin(JX, yy, "l", str(i + 1), stub=0)
    for i in range(4):
        w((EX + EW + 14, ys[i + 2]), (JX, ys[i + 2]))
    flag(JX - 6, ys[0], "+3V3", side="l", col="#c0392b"); w((JX - 6, ys[0]), (JX, ys[0]))
    flag(JX - 6, ys[1], "GND", side="l", col="#333"); w((JX - 6, ys[1]), (JX, ys[1]))
    for i, lab in enumerate(["3V3", "GND", "TX", "RX", "DTR", "DCD"]):
        t(JX + 44, ys[i] + 4, lab, FS - 3, "end", fill="#555")
    # carrier
    CX, CW = 1290, 230
    box(CX, ys[0] - 40, CW, 6 * 28 + 50, cname, None, fill="#fff8e6")
    t(CX + CW / 2, ys[0] - 10, "HW-027 MAX3232 on stripboard", FS - 2, "middle", fill="#555")
    ttl = ["+ VCC (16)", "− GND (15)", "T2IN (10)", "R2OUT (9)", "T1IN (11)", "R1OUT (12)"]
    for i, (yy, lab) in enumerate(zip(ys, ttl)):
        pin(CX, yy, "l", lab, num=i + 1)
        w((JX + 48, yy), (CX - 14, yy))
    rs = [("R1IN (13)", "DCD"), ("R2IN (8)", "RxD"), ("T2OUT (7)", "TxD"), ("T1OUT (14)", "DTR"), ("− GND", "GND")]
    rys = [ys[0] + 14 + i * 28 for i in range(5)]
    for (lab, _), yy in zip(rs, rys):
        pin(CX + CW, yy, "r", lab)
    t(CX + CW / 2, ys[5] + 22, "ch2: 10→7, 8→9   ch1: 11→14, 13→12", FS - 3, "middle", fill="#555")
    # DB9 male (box panel)
    DX = 1590
    box(DX, rys[0] - 26, 56, 5 * 28 + 30, "DB9 M", None)
    for i, yy in enumerate(rys):
        pin(DX, yy, "l", str(i + 1), stub=0)
        w((CX + CW + 14, yy), (DX, yy))
        t(DX + 50, yy + 4, rs[i][1], FS - 3, "end", fill="#555")
    t(DX + 28, rys[4] + 22, "6–9 n.c.", FS - 3, "middle", fill="#555")
    t((CX + CW + DX) / 2, rys[4] + 24, "ribbon", FS - 3, "middle", fill="#555")
    # cable to DB25
    KX = 1730
    for i, (yy, p25) in enumerate(zip(rys, [8, 3, 2, 20, 7])):
        w((DX + 56, yy), (KX, yy), col="#555", width=2.4)
        t(KX - 6, yy - 3, f"{i+1}→{p25}", FS - 3, "end", fill="#555")
    t((DX + 56 + KX) / 2, rys[4] + 36, "DB9F→DB25M", FS - 3, "middle", fill="#555")
    # courier
    box(KX, rys[0] - 40, 230, 5 * 28 + 70, courier, power, fill="#eaf7ee")
    for yy, p25, nm in zip(rys, [8, 3, 2, 20, 7], ["DCD", "RxD", "TxD", "DTR", "GND"]):
        t(KX + 8, yy + 4 + 30, "", FS)
    for i, (yy, p25, nm) in enumerate(zip(rys, [8, 3, 2, 20, 7], ["DCD", "RxD", "TxD", "DTR", "SG"])):
        t(KX + 6, yy + 4, f"DB25 {p25} {nm}", FS - 2)
    for i, line in enumerate(extra):
        t(KX + 120, rys[0] + 30 + i * 14, line, FS - 3, fill="#444")
    return KX, rys

Y1 = 345
KX, rys1 = chain(Y1, "dialer", [17, 16, 18, 19], ["B10", "B9", "B12", "B13"], "J1", "[P3–P8]",
                 "Carrier #1 (dialer)", "Courier V.Everything", ["= DIALER", "own AC adapter"],
                 ["DIP 3,5,8 down", "NVRAM &H0&R1", "speaker = alarm"])
Y2 = 575
_, rys2 = chain(Y2, "answerer", [32, 33, 21, 22], ["L14", "L13", "B15", "B18"], "J2", "[P12–P17]",
                "Carrier #2 (answerer)", "Courier V.Everything 56K", ["= ANSWERER (R20.0013.00)", "own AC adapter"],
                ["auto-answer off", "ESP sends ATA"])

# ---------------------------------------------------------------- line board
YDAC = 940
pin(EX + EW, 765, "r", "GPIO25 DAC1 [L12]")
w((EX + EW + 14, 765), (1130, 765), (1130, YDAC), (1170, YDAC))
pin(EX + EW, 795, "r", "GPIO27 [L10] (spare)")
w((EX + EW + 14, 795), (1145, 795))
# J3
J3X = 1170
ys3 = [YDAC + i * 28 for i in range(6)]
box(J3X, ys3[0] - 24, 48, 6 * 28 + 20, "J3", None)
t(J3X + 24, ys3[5] + 30, "[Z3–Z8]", FS - 3, "middle", fill="#555")
for i, (yy, lab) in enumerate(zip(ys3, ["DAC", "GND", "+12V", "+5V", "IO27", "GND"])):
    pin(J3X, yy, "l", str(i + 1), stub=0)
    t(J3X + 44, yy + 4, lab, FS - 3, "end", fill="#555")
w((1145, 795), (1145, ys3[4]), (J3X, ys3[4]))
for k, nm, col in ((1, "GND", "#333"), (2, "+12V", "#8e44ad"), (3, "+5V", "#e67e22"), (5, "GND", "#333")):
    w((J3X - 60, ys3[k]), (J3X, ys3[k])); flag(J3X - 60, ys3[k], nm, side="l", col=col)

frame(1240, 880, 560, 350, "Line board (stripboard 7 × 12, stands in J3)", "#2a5db0")
LX = 1240
# header pins on the line board side
hdr = ["{F12} DAC", "{E12} GND", "{D12} +12V", "{C12} pulled", "{B12} pulled", "{A12} GND"]
for yy, lab in zip(ys3, hdr):
    w((J3X + 48, yy), (LX + 8, yy), col="#111" if "pulled" not in lab else "#bbb", dash=None if "pulled" not in lab else "4,3")
    t(LX + 12, yy + 4, lab, FS - 3, fill="#2a5db0" if "pulled" not in lab else "#999")
# primary: DAC -> R 680 -> C 10u -> T1.1
TX1, TX2 = 1580, 1630
res(LX + 80, ys3[0], 1420, "LR1 680 Ω {F11–B11}")
cap(1420, ys3[0], 1500, "LC1 10 µF {B10+ C10−}", polar=True)
w((1500, ys3[0]), (TX1, ys3[0]))
# transformer coils
def coil(x, ya, yb, right):
    n = 4; h = (yb - ya) / n
    d = f"M {x} {ya} "
    for i in range(n):
        y1 = ya + i * h
        d += f"A {h/2} {h/2} 0 0 {1 if right else 0} {x} {y1 + h} "
    S.append(f'<path d="{d}" fill="none" stroke="#111" stroke-width="1.8"/>')
YT1, YT3 = ys3[0], ys3[0] + 100
coil(TX1, YT1, YT3, True); coil(TX2, YT1, YT3, False)
w((TX1 + 16, YT1 - 4), (TX1 + 16, YT3 + 4), width=1.6); w((TX2 - 16, YT1 - 4), (TX2 - 16, YT3 + 4), width=1.6)
t(TX1 - 30, YT1 + 62, "T1 SM-LP-5001", FS - 2, "end", "bold")
t(TX1 - 30, YT1 + 76, "600:600, pins 2/5", FS - 3, "end", fill="#555")
t(TX1 - 30, YT1 + 88, "clipped (n.c.)", FS - 3, "end", fill="#555")
t(TX1 - 6, YT1 - 6, "1 {C9}", FS - 3, "end"); t(TX1 - 6, YT3 + 14, "3 {E9}", FS - 3, "end")
t(TX2 + 6, YT1 - 6, "6 {C3}", FS - 3); t(TX2 + 6, YT3 + 14, "4 {E3}", FS - 3)
S.append(f'<circle cx="{TX1 - 6}" cy="{YT1 + 6}" r="2.5" fill="#111"/>'); S.append(f'<circle cx="{TX2 + 6}" cy="{YT1 + 6}" r="2.5" fill="#111"/>')
# pin 3 -> GND (strip E lower = J3.2)
w((TX1, YT3), (TX1, YT3 + 10)); gnd(TX1, YT3 + 10)
# secondary: pin6 -> RD ; pin4 -> C2 -> TIP
YRD, YTIP, YRA = YT1, YT3, ys3[5] + 30
w((TX2, YT1), (1760, YT1)); dot(1700, YT1)
t(1730, YT1 - 6, "RD {C}", FS - 2, "middle", "bold", "#2a5db0")
cap(TX2, YT3, 1720, "LC2 1 µF MKS2 {E1–G1}")
w((1720, YT3), (1760, YT3))
t(1740, YT3 - 6, "TIP {G}", FS - 2, "middle", "bold", "#2a5db0")
# JP1 + R2
JY = ys3[5] + 50
jx = [1400, 1440, 1480, 1520]
for x, lab in zip(jx, ["A", "B", "C", "D"]):
    S.append(f'<rect x="{x-6}" y="{JY-6}" width="12" height="12" fill="#f1c40f" stroke="#111"/>')
    t(x, JY + 22, lab, FS - 2, "middle", "bold")
t(1460, JY + 38, "JP1 {A1–D1}", FS - 2, "middle", "bold")
t(1460, JY + 52, "no feed: B–C   feed: A–B + C–D", FS - 3, "middle", fill="#444")
# A -> R2 -> GND
res(jx[0], JY, 1310, "LR2 470 Ω {A5–A7}", vertical=False)
gnd(1310, JY)
# B -> RA ; C -> RD ; D -> +12V
w((jx[1], JY - 6), (jx[1], JY - 30), (1760, JY - 30))
t(1730, JY - 36, "RA {B}", FS - 2, "middle", "bold", "#2a5db0")
w((jx[2], JY - 6), (jx[2], JY - 50), (1700, JY - 50), (1700, YT1)); dot(1700, YT1)
w((jx[3], JY + 6), (jx[3], JY + 14), (1540, JY + 14), (1540, JY + 68), (1300, JY + 68)); flag(1300, JY + 68, "+12V {D}", side="l", col="#8e44ad")
# line wires to the jack board
JBX = 1830
frame(JBX, 880, 170, 350, "Jack board", "#2a5db0")
box(JBX + 20, 920, 130, 100, "Dialer LINE", ["RJ 6P4C, front left", "JST, pos 3/4"])
box(JBX + 20, 1080, 130, 100, "Answerer LINE", ["RJ 6P4C, front right", "JST, pos 3/4"])
YDj = [YT1, YT3]; YAj = [1060, 1100]
w((1760, YT1), (JBX + 20, YT1)); t(1795, YT1 - 4, "{C2}", FS - 3, "middle", fill="#555")
w((1760, YT3), (1810, YT3), (1810, 1000), (JBX + 20, 1000)); dot(1810, 1040)
t(1795, YT3 - 4, "{G3}", FS - 3, "middle", fill="#555")
w((1810, 1000), (1810, 1150), (JBX + 20, 1150)); t(1822, 1145, "{G4}", FS - 3, fill="#555")
w((1760, JY - 30), (1790, JY - 30), (1790, 1110), (JBX + 20, 1110)); t(1778, 1106, "{B3}", FS - 3, "middle", fill="#555")
t(JBX + 85, 1210, "pairs: polarity free", FS - 3, "middle", fill="#555")
# RJ cords up to the Couriers
for i, (yy, ytop) in enumerate(((970, rys1[-1] + 45), (1130, rys2[-1] + 45))):
    xr = 2030 + i * 18
    w((JBX + 150, yy), (xr, yy), (xr, ytop), (1960, ytop), col="#2a5db0", width=2.6)
t(1995, rys1[-1] + 40, "RJ cord", FS - 3, "middle", fill="#2a5db0")
t(1995, rys2[-1] + 40, "RJ cord", FS - 3, "middle", fill="#2a5db0")
t(1735, rys1[-1] + 40, "LINE jack (centre pair)", FS - 2, fill="#2a5db0")
t(1735, rys2[-1] + 40, "LINE jack (centre pair)", FS - 2, fill="#2a5db0")

# ---------------------------------------------------------------- notes
notes = [
    "Power: +12 V only feeds U1 and the line board (JP1 loop feed). ESP32 runs from U1 5 V → 5V pin; its 3V3 feeds both MAX3232 carriers. All grounds common.",
    "RS232: box = DTE (DB9 male), straight DB9F→DB25M modem cables. MAX3232 inverts: GPIO low = DTR on; DCD low = carrier. RTS/CTS not wired (&H0&R1).",
    "Dial tone: GPIO25 DAC (DMA, 8 kHz) → LR1 → LC1 → T1 primary; secondary across dialer TIP/RD via LC2. DAC hi-Z when idle.",
    "Loop feed (JP1 A–B + C–D): +12 V on the dialer leg (RD), answerer leg (RA) to GND via LR2 470 Ω. Default: B–C only, no DC on the line.",
]
for i, n in enumerate(notes):
    t(30, 1262 + i * 18, n, FS - 1, fill="#333")

def build():
    W, H = 2080, 1340
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#111"/>' for x, y in DOTS)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="DejaVu Sans, sans-serif">\n'
            f'<rect width="100%" height="100%" fill="#fff"/>\n' + "\n".join(S) + dots + "\n</svg>\n")

if __name__ == "__main__":
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notes", "schematic.svg")
    open(p, "w").write(build())
    print("wrote", os.path.normpath(p))
