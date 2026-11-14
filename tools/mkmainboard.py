#!/usr/bin/env python3
"""Draw the main perfboard layout (notes/mainboard.svg). Stdlib only.
Grid: 26 columns A..Z x 31 rows 1..31 (2.54 mm). Component side view + solder side (mirrored) view."""
import os

COLS, ROWS, P = 26, 31, 18
L = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def xy(c, r):            # 'B', 2 -> grid index
    return L.index(c), r - 1

NETS = {  # name: colour
    "3V3": "#c0392b", "GND": "#333", "5V": "#e67e22", "12V": "#8e44ad",
    "SIG": "#1b7f3b", "LINE": "#2a5db0", "LED": "#b8860b",
}
# ESP32 DevKit (USB toward row 1), pin n at row n+1
ESP_B = ["CLK", "D0", "D1", "15", "2", "0", "4", "16", "17", "5", "18", "19", "GND", "21", "RX", "TX", "22", "23", "GND"]
ESP_L = ["5V", "CMD", "D3", "D2", "13", "GND", "12", "14", "27", "26", "25", "33", "32", "35", "34", "VN", "VP", "EN", "3V3"]

# connectors: (label, column, first row, [(pin name, net)], horizontal?)
CONN = [
    ("J1 dialer carrier (socket, carrier stands up)", "P", 3,
     [("3V3", "3V3"), ("GND", "GND"), ("TX 17", "SIG"), ("RX 16", "SIG"), ("DTR 18", "SIG"), ("DCD 19", "SIG")], False),
    ("J2 answerer carrier (socket, carrier stands up)", "P", 12,
     [("3V3", "3V3"), ("GND", "GND"), ("TX 32", "SIG"), ("RX 33", "SIG"), ("DTR 21", "SIG"), ("DCD 22", "SIG")], False),
    ("J3 line board (socket, stands up)", "Z", 3,
     [("DAC 25", "LINE"), ("GND", "GND"), ("+12V", "12V"), ("+5V", "5V"), ("GPIO27", "LINE"), ("GND", "GND")], False),
    ("J4 power in", "P", 30, [("+12V", "12V"), ("GND", "GND"), ("+5V", "5V"), ("GND", "GND")], True),
    ("J6 RING", "U", 30, [("GPIO4", "SIG"), ("GND", "GND")], True),
    ("J5 LED", "X", 30, [("LED+", "LED"), ("LED−", "GND")], True),
]
PARTS = [  # (label, (col,row) a, (col,row) b, colour)
    ("R1 330 Ω", ("X", 24), ("X", 28), NETS["LED"]),
    ("C1 470 µF (+ top)", ("O", 20), ("O", 21), NETS["3V3"]),
]
# wiring list: (net, from, to, note)
WIRES = [
    ("3V3", "L20", "O20", "ESP 3V3 → C1 +"), ("3V3", "O20", "P3", "→ J1.1"), ("3V3", "P3", "P12", "→ J2.1"),
    ("GND", "B20", "O21", "ESP GND → C1 −"), ("GND", "O21", "P4", "→ J1.2"), ("GND", "P4", "P13", "→ J2.2"),
    ("GND", "P13", "Z4", "→ J3.2"), ("GND", "Z4", "Z8", "J3.2 → J3.6"), ("GND", "O21", "Q30", "→ J4.2"),
    ("GND", "Q30", "S30", "J4.2 → J4.4"), ("GND", "S30", "V30", "→ J6.2"), ("GND", "V30", "Y30", "→ J5.2"),
    ("GND", "B14", "L7", "ESP GND pins tied (optional, under the ESP)"),
    ("5V", "R30", "L2", "buck +5V → ESP 5V"), ("5V", "R30", "Z6", "→ J3.4"),
    ("12V", "P30", "Z5", "J4.1 → J3.3"),
    ("SIG", "B10", "P5", "GPIO17 → J1.3 TX"), ("SIG", "B9", "P6", "GPIO16 → J1.4 RX"),
    ("SIG", "B12", "P7", "GPIO18 → J1.5 DTR"), ("SIG", "B13", "P8", "GPIO19 → J1.6 DCD"),
    ("SIG", "L14", "P14", "GPIO32 → J2.3 TX"), ("SIG", "L13", "P15", "GPIO33 → J2.4 RX"),
    ("SIG", "B15", "P16", "GPIO21 → J2.5 DTR"), ("SIG", "B18", "P17", "GPIO22 → J2.6 DCD"),
    ("LINE", "L12", "Z3", "GPIO25 DAC → J3.1"), ("LINE", "L10", "Z7", "GPIO27 → J3.5 (relay, spare)"),
    ("SIG", "B8", "U30", "GPIO4 → J6.1 RING"),
    ("LED", "B6", "X24", "GPIO2 → R1"), ("LED", "X28", "X30", "R1 → J5.1 LED + (short link or bent leg)"),
]

def parse(s):
    return L.index(s[0]), int(s[1:]) - 1

def view(ox, oy, mirror, title):
    g = []
    def X(c): return ox + ((COLS - 1 - c) if mirror else c) * P
    def Y(r): return oy + r * P
    W, H = (COLS - 1) * P, (ROWS - 1) * P
    g.append(f'<text x="{ox + W/2}" y="{oy - 52}" text-anchor="middle" font-weight="bold" font-size="15">{title}</text>')
    g.append(f'<rect x="{ox - P*1.2}" y="{oy - P*2.2}" width="{W + P*2.4}" height="{H + P*4.4}" rx="6" fill="#e9dcb8" stroke="#a08a50"/>')
    for c in range(COLS):
        g.append(f'<text x="{X(c)}" y="{oy - 8}" text-anchor="middle" font-size="9" fill="#666">{L[c]}</text>')
    for r in range(ROWS):
        g.append(f'<text x="{ox - P*1.2 - 4 if not mirror else ox + W + P*1.2 + 4}" y="{Y(r) + 3}" text-anchor="{"end" if not mirror else "start"}" font-size="9" fill="#666">{r + 1}</text>')
    for c in range(COLS):
        for r in range(ROWS):
            g.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="2.2" fill="#c8a85a"/>')
    # mounting holes: 83.7 x 64.6 mm centre to centre (measured), assumed centred on the hole grid
    mx, my = (64.6 - 63.5) / 2 / 2.54, (83.7 - 76.2) / 2 / 2.54     # offsets past A/Z and rows 1/31, in holes
    for cx, cy in ((-mx, -my), (COLS - 1 + mx, -my), (-mx, ROWS - 1 + my), (COLS - 1 + mx, ROWS - 1 + my)):
        hx = ox + ((COLS - 1 - cx) if mirror else cx) * P
        g.append(f'<circle cx="{hx}" cy="{oy + cy * P}" r="{P * 0.63}" fill="#fff" stroke="#a08a50" stroke-width="1.2"/>')
    # ESP32 outline (PCB from just above row 1 to row ~20.5, antenna to ~row 23.5)
    xb, xl = X(1), X(11)
    x0, x1 = min(xb, xl) - P*0.75, max(xb, xl) + P*0.75
    g.append(f'<rect x="{x0}" y="{Y(0) - P*0.55}" width="{x1 - x0}" height="{P*20.0}" fill="none" stroke="#000" stroke-width="1.5" stroke-dasharray="5,3"/>')
    g.append(f'<rect x="{x0 + P*1.8}" y="{Y(19.4)}" width="{x1 - x0 - P*3.6}" height="{P*3.0}" fill="#ddd" fill-opacity="0.5" stroke="#777" stroke-dasharray="3,3"/>')
    g.append(f'<text x="{(x0+x1)/2}" y="{Y(21.2)}" text-anchor="middle" font-size="10" fill="#555">antenna: keep clear</text>')
    g.append(f'<rect x="{(x0+x1)/2 - 22}" y="{Y(0) - P*1.15}" width="44" height="{P*0.9}" fill="#bbb" stroke="#777"/>')
    g.append(f'<text x="{(x0+x1)/2}" y="{Y(0) - P*0.5}" text-anchor="middle" font-size="9">USB</text>')
    g.append(f'<text x="{(x0+x1)/2}" y="{Y(9)}" text-anchor="middle" font-size="13" fill="#555">ESP32 DevKit</text>')
    g.append(f'<text x="{(x0+x1)/2}" y="{Y(9.9)}" text-anchor="middle" font-size="10" fill="#555">in 2× 19-pin female headers</text>')
    for i, n in enumerate(ESP_B):
        net = "GND" if n == "GND" else ("SIG" if n in ("16", "17", "18", "19", "21", "22", "4") else ("LED" if n == "2" else None))
        col = NETS.get(net, "#999")
        g.append(f'<rect x="{xb - 6}" y="{Y(i+1) - 6}" width="12" height="12" fill="{col}" fill-opacity="{1 if net else 0.25}"/>')
        g.append(f'<text x="{xb + (-10 if not mirror else 10) * -1}" y="{Y(i+1) + 4}" text-anchor="{"start" if not mirror else "end"}" font-size="9">{n}</text>')
    for i, n in enumerate(ESP_L):
        net = {"GND": "GND", "3V3": "3V3", "5V": "5V", "25": "LINE", "27": "LINE", "32": "SIG", "33": "SIG"}.get(n)
        col = NETS.get(net, "#999")
        g.append(f'<rect x="{xl - 6}" y="{Y(i+1) - 6}" width="12" height="12" fill="{col}" fill-opacity="{1 if net else 0.25}"/>')
        g.append(f'<text x="{xl + (-10 if not mirror else 10)}" y="{Y(i+1) + 4}" text-anchor="{"end" if not mirror else "start"}" font-size="9">{n}</text>')
    for label, c, r0, pins, horiz in CONN:
        ci = L.index(c)
        def pos(k):
            return (X(ci + k), Y(r0 - 1)) if horiz else (X(ci), Y(r0 - 1 + k))
        (ax, ay), (bx, by) = pos(0), pos(len(pins) - 1)
        g.append(f'<rect x="{min(ax, bx) - 9}" y="{min(ay, by) - 9}" width="{abs(bx - ax) + 18}" height="{abs(by - ay) + 18}" fill="none" stroke="#000" stroke-width="1.3"/>')
        for k, (pn, net) in enumerate(pins):
            px, py = pos(k)
            g.append(f'<rect x="{px - 6}" y="{py - 6}" width="12" height="12" fill="{NETS[net]}"/>')
            g.append(f'<text x="{px}" y="{py + 3.5}" text-anchor="middle" font-size="8" fill="#fff">{k+1}</text>')
            if not mirror:
                if horiz:
                    g.append(f'<text x="{px + 3}" y="{py - 12}" font-size="8" fill="{NETS[net]}" transform="rotate(-90 {px + 3} {py - 12})">{pn}</text>')
                else:
                    g.append(f'<text x="{px + (-14 if c == "Z" else 14)}" y="{py + 4}" text-anchor="{"end" if c == "Z" else "start"}" font-size="9" fill="{NETS[net]}">{pn}</text>')
        if not mirror:
            name = label.split(" (")[0]
            if horiz:
                g.append(f'<text x="{(ax + bx)/2}" y="{ay + 26}" text-anchor="middle" font-size="10" font-weight="bold">{name}</text>')
            elif c == "Z":
                g.append(f'<text x="{ax + 10}" y="{ay - 14}" text-anchor="end" font-size="10" font-weight="bold">{name}</text>')
            else:
                g.append(f'<text x="{ax - 12}" y="{ay - 12}" font-size="10" font-weight="bold">{name}</text>')
        if label.startswith(("J1", "J2")) and not mirror:
            g.append(f'<rect x="{ax + 2}" y="{ay - P*0.9}" width="{P*0.25}" height="{P*6.8}" fill="#2a5db0" fill-opacity="0.35"/>')
        if label.startswith("J3") and not mirror:
            g.append(f'<rect x="{ax - 1}" y="{ay - P*1.2}" width="{P*0.25}" height="{P*25}" fill="#8e44ad" fill-opacity="0.3"/>')
            g.append(f'<text x="{ax - 8}" y="{Y(17)}" text-anchor="middle" font-size="10" fill="#8e44ad" transform="rotate(-90 {ax - 8} {Y(17)})">line board stands here, parts face out →</text>')
    for label, a, b, col in PARTS:
        (ca, ra), (cb, rb) = xy(*a), xy(*b)
        g.append(f'<line x1="{X(ca)}" y1="{Y(ra)}" x2="{X(cb)}" y2="{Y(rb)}" stroke="{col}" stroke-width="5" stroke-linecap="round"/>')
        for c, r in ((ca, ra), (cb, rb)):
            g.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="4.5" fill="{col}"/>')
        if not mirror:
            g.append(f'<text x="{(X(ca)+X(cb))/2 + (0 if ra == rb else 10)}" y="{(Y(ra)+Y(rb))/2 + (16 if ra == rb else 4)}" text-anchor="{"middle" if ra == rb else "start"}" font-size="10" fill="{col}">{label}</text>')
    if mirror:
        for net, a, b, _ in WIRES:
            (ca, ra), (cb, rb) = parse(a), parse(b)
            g.append(f'<line x1="{X(ca)}" y1="{Y(ra)}" x2="{X(cb)}" y2="{Y(rb)}" stroke="{NETS[net]}" stroke-width="1.6" stroke-opacity="0.8"/>')
    return g

out = []
W1 = (COLS - 1) * P + 120
vx2 = 60 + W1 + 40
tx = vx2 + W1
Ht = (ROWS - 1) * P + 260
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{tx + 560}" height="{Ht}" font-family="DejaVu Sans, sans-serif" font-size="12">')
out.append('<rect width="100%" height="100%" fill="#fff"/>')
out.append('<text x="20" y="30" font-size="20" font-weight="bold">Main board: perfboard, 26 × 31 holes, mounting holes 83.7 × 64.6 mm</text>')
out.append('<text x="20" y="52" fill="#555">Draft 2026-11-12, generated by tools/mkmainboard.py. Coordinates = column letter + row number (A1 top left, component side).</text>')
out += view(70, 135, False, "Component side (parts on top)")
out += view(vx2, 135, True, "Solder side (flipped left↔right): wires, point to point")
# legend + wiring table
y = 110
out.append(f'<text x="{tx}" y="{y - 34}" font-weight="bold" font-size="15">Wiring list (on the solder side)</text>')
for net, a, b, note in WIRES:
    out.append(f'<rect x="{tx}" y="{y - 9}" width="10" height="10" fill="{NETS[net]}"/>')
    out.append(f'<text x="{tx + 16}" y="{y}"><tspan font-weight="bold">{a} → {b}</tspan>  {note}</text>')
    y += 17
y += 14
for t in ["Carriers stand upright in J1/J2 (blue strip = carrier, MAX3232 side facing away from the ESP32).",
          "Line board (stripboard 25 × 12) stands upright in J3 along the right edge (purple),",
          "  its parts facing out over the board edge; line pairs: JST 2-pin from it to each RJ12 board.",
          "The case gets ~70 mm tall for the standing boards (decided 2026-11-12).",
          "J4: +12 V from the rocker, +5 V/GND from the LM2596 (buck on its own pads).",
          "J4/J5/J6: JST (keyed, latching) male on the board, leads to the panel parts with JST female.",
          "Lines on the solder side = insulated wires.",
          "Under the antenna (grey): no parts, no wires.",
          "Mounting holes (white): 83.7 × 64.6 mm centre to centre (measured; assumed centred on the grid)."]:
    out.append(f'<text x="{tx}" y="{y}" fill="#555" font-size="11">{t}</text>')
    y += 16
out.append('</svg>')
d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notes", "mainboard.svg")
open(d, "w").write("\n".join(out))
print("wrote", os.path.normpath(d))
