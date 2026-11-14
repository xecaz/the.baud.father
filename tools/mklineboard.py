#!/usr/bin/env python3
"""Line board (dial tone injection + optional loop feed) on stripboard: draw notes/lineboard.svg and
check the copper against the intended netlist. Stdlib only.

Board: 7 strips (A..G) x 12 holes (rows 1..12), cut from the 12 x 25 stripboard. Strips run vertically
(along the 12 holes). The board stands in J3 with row 12 at the bottom edge (bent header pins down) and the
parts facing out of the main board. Component side view: A on the left = toward the case front."""
import os, sys

COLS, ROWS, P = "ABCDEFG", 12, 26
CUTS = ["A6", "B6", "C6", "E6"]            # drill these holes (copper side; any time)

# header into J3 (row 12). J3.1 is nearest the main board's row 1 (back wall) = rightmost here.
HEADER = {"A12": "J3.6 GND", "B12": "J3.5 GPIO27 (pull this pin)", "C12": "J3.4 +5V (pull this pin)",
          "D12": "J3.3 +12V", "E12": "J3.2 GND", "F12": "J3.1 DAC GPIO25"}
PULLED = {"B12", "C12"}
# nets that the main board joins outside this board
EXTERNAL = {"A12": "GND", "E12": "GND", "D12": "12V", "F12": "DAC"}

# parts: (ref, label, [(hole, pin name)], kind)
PARTS = [
    ("T1", "SM-LP-5001", [("C9", "1"), ("D9", "2 NC"), ("E9", "3"), ("C3", "6"), ("D3", "5 NC"), ("E3", "4")], "xfmr"),
    ("R1", "680 Ω", [("F11", "a"), ("B11", "b")], "res"),
    ("C1", "10 µF", [("B10", "+"), ("C10", "−")], "ecap"),
    ("C2", "1 µF film", [("E1", "a"), ("G1", "b")], "fcap"),
    ("R2", "470 Ω", [("A5", "a"), ("A7", "b")], "res_stand"),
    ("JP1", "loop feed", [("A1", "R2"), ("B1", "RA"), ("C1", "RD"), ("D1", "+12V")], "hdr"),
    ("W1", "dialer RD wire", [("C2", "")], "wire"),
    ("W2", "answerer RA wire", [("B3", "")], "wire"),
    ("W3", "dialer TIP wire", [("G3", "")], "wire"),
    ("W4", "answerer TIP wire", [("G4", "")], "wire"),
]
NC_PINS = {"D9", "D3"}   # T1 pins 2/5: not connected inside, do not solder (or clip them)

# intended netlist: net -> set of "REF.pin" (and header holes)
WANT = {
    "DAC": {"HDR.F12", "R1.a"},
    "X": {"R1.b", "C1.+"},
    "P1": {"C1.−", "T1.1"},
    "GND": {"T1.3", "HDR.E12", "HDR.A12", "R2.b"},
    "RD": {"T1.6", "JP1.RD", "W1."},
    "S4": {"T1.4", "C2.a"},
    "TIP": {"C2.b", "W3.", "W4."},
    "RA": {"JP1.RA", "W2."},
    "R2": {"R2.a", "JP1.R2"},
    "12V": {"HDR.D12", "JP1.+12V"},
}

def hole(h): return COLS.index(h[0]), int(h[1:])

def segments():
    """strip segment id for every hole (cut holes -> None)"""
    seg = {}
    for c in COLS:
        k = 0
        for r in range(1, ROWS + 1):
            h = f"{c}{r}"
            if h in CUTS: seg[h] = None; k += 1; continue
            seg[h] = f"{c}:{k}"
    return seg

def check():
    seg = segments()
    pins = {}   # "REF.pin" -> segment
    for h in HEADER:
        if h in PULLED: continue
        pins[f"HDR.{h}"] = seg[h]
    for ref, _, pl, kind in PARTS:
        for h, name in pl:
            if h in NC_PINS: continue
            assert seg[h] is not None, f"{ref} pin on a cut hole {h}"
            pins[f"{ref}.{name.split()[0] if name else ''}"] = seg[h]
    # union: segments joined outside (main board GND)
    parent = {}
    def f(x):
        parent.setdefault(x, x)
        while parent[x] != x: x = parent[x]
        return x
    def u(a, b): parent[f(a)] = f(b)
    gnd = [seg[h] for h, n in EXTERNAL.items() if n == "GND"]
    for s in gnd[1:]: u(gnd[0], s)
    got = {}
    for p, s in pins.items(): got.setdefault(f(s), set()).add(p)
    ok = True
    want = {frozenset(v) for v in WANT.values()}
    for s, ps in got.items():
        if frozenset(ps) not in want:
            print("MISMATCH", s, sorted(ps)); ok = False
    for n, v in WANT.items():
        if frozenset(v) not in {frozenset(x) for x in got.values()}:
            print("MISSING net", n, sorted(v)); ok = False
    # nothing else may sit on a used segment by accident: NC pins and pulled pins
    for h in NC_PINS:
        print(f"note: T1 NC pin at {h} is on segment {seg[h]} ({[n for n,v in WANT.items() if any(pins.get(p)==seg[h] for p in v)]})")
    print("netlist OK" if ok else "netlist FAILED")
    return ok

def svg():
    W, H = (len(COLS) - 1) * P, (ROWS - 1) * P
    out = []
    def view(ox, oy, mirror, title, solder):
        X = lambda c: ox + ((len(COLS) - 1 - c) if mirror else c) * P
        Y = lambda r: oy + (r - 1) * P
        out.append(f'<text x="{ox + W/2}" y="{oy - 40}" text-anchor="middle" font-weight="bold" font-size="15">{title}</text>')
        out.append(f'<rect x="{ox - P*0.7}" y="{oy - P*0.7}" width="{W + P*1.4}" height="{H + P*1.4}" rx="4" fill="#e9dcb8" stroke="#a08a50"/>')
        for i, c in enumerate(COLS):
            out.append(f'<text x="{X(i)}" y="{oy - 22}" text-anchor="middle" font-size="11" fill="#555">{c}</text>')
            if solder:
                out.append(f'<rect x="{X(i) - P*0.36}" y="{oy - P*0.6}" width="{P*0.72}" height="{H + P*1.2}" fill="#d08a45" opacity="0.75"/>')
        for r in range(1, ROWS + 1):
            tx = ox - P*0.7 - 6 if not mirror else ox + W + P*0.7 + 6
            out.append(f'<text x="{tx}" y="{Y(r) + 4}" text-anchor="{"end" if not mirror else "start"}" font-size="10" fill="#555">{r}</text>')
        for i, c in enumerate(COLS):
            for r in range(1, ROWS + 1):
                h = f"{c}{r}"
                if h in CUTS:
                    out.append(f'<circle cx="{X(i)}" cy="{Y(r)}" r="{P*0.42}" fill="#fff" stroke="#c0392b" stroke-width="2.5"/>')
                    out.append(f'<line x1="{X(i)-7}" y1="{Y(r)-7}" x2="{X(i)+7}" y2="{Y(r)+7}" stroke="#c0392b" stroke-width="2.5"/>')
                    out.append(f'<line x1="{X(i)-7}" y1="{Y(r)+7}" x2="{X(i)+7}" y2="{Y(r)-7}" stroke="#c0392b" stroke-width="2.5"/>')
                else:
                    out.append(f'<circle cx="{X(i)}" cy="{Y(r)}" r="2.6" fill="#555"/>')
        def at(h):
            c, r = hole(h); return X(c), Y(r)
        if solder:
            for h in HEADER:
                x, y = at(h)
                if h in PULLED:
                    out.append(f'<circle cx="{x}" cy="{y}" r="6" fill="none" stroke="#888" stroke-dasharray="2,2"/>')
                else:
                    out.append(f'<circle cx="{x}" cy="{y}" r="6" fill="#bbb" stroke="#333"/>')
            for ref, lab, pl, kind in PARTS:
                for h, n in pl:
                    if h in NC_PINS: continue
                    x, y = at(h)
                    out.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#bbb" stroke="#333"/>')
            return
        # component side: header
        xa, _ = at("A12"); xf, y12 = at("F12")
        out.append(f'<rect x="{xa - P*0.45}" y="{y12 - P*0.45}" width="{xf - xa + P*0.9}" height="{P*0.9}" fill="#222" opacity="0.85"/>')
        for h in HEADER:
            x, y = at(h)
            col = "#777" if h in PULLED else "#f1c40f"
            out.append(f'<rect x="{x-3}" y="{y-3}" width="6" height="6" fill="{col}"/>')
        for ref, lab, pl, kind in PARTS:
            pts = [at(h) for h, _ in pl]
            if kind == "xfmr":
                (x1, y1), (x3, _) = pts[0], pts[2]
                _, y6 = pts[3]
                out.append(f'<rect x="{x1 - P*0.85}" y="{y6 + P*0.55}" width="{x3 - x1 + P*1.7}" height="{y1 - y6 - P*1.1}" rx="3" fill="#2c3e50" opacity="0.9"/>')
                for (x, y), (h, n) in zip(pts, pl):
                    nc = h in NC_PINS
                    out.append(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" fill="{"#999" if nc else "#ddd"}" stroke="#333"/>')
                    out.append(f'<text x="{x}" y="{y + (P*0.55 if y > y6 + 1 else -P*0.42)}" text-anchor="middle" font-size="9" fill="#000">{n}</text>')
                cx = (x1 + x3) / 2
                out.append(f'<circle cx="{x1 - P*0.5}" cy="{y1 - P*0.9}" r="2.5" fill="#fff"/>')
                out.append(f'<text x="{cx}" y="{(y1 + y6)/2 - 4}" text-anchor="middle" font-size="11" fill="#fff" font-weight="bold">T1</text>')
                out.append(f'<text x="{cx}" y="{(y1 + y6)/2 + 10}" text-anchor="middle" font-size="9" fill="#fff">SM-LP-5001</text>')
                out.append(f'<text x="{cx}" y="{(y1 + y6)/2 + 22}" text-anchor="middle" font-size="8" fill="#ccc">dot = pin 1</text>')
            elif kind in ("res", "res_stand"):
                (xa_, ya_), (xb_, yb_) = pts
                out.append(f'<line x1="{xa_}" y1="{ya_}" x2="{xb_}" y2="{yb_}" stroke="#777" stroke-width="2"/>')
                mx, my = (xa_ + xb_) / 2, (ya_ + yb_) / 2
                if ya_ == yb_:
                    out.append(f'<rect x="{mx - 26}" y="{my - 7}" width="52" height="14" rx="6" fill="#d6c08a" stroke="#806a30"/>')
                    out.append(f'<text x="{mx}" y="{my + 4}" text-anchor="middle" font-size="10">{ref} {lab}</text>')
                else:
                    out.append(f'<circle cx="{xa_}" cy="{ya_}" r="8" fill="#d6c08a" stroke="#806a30"/>')
                    out.append(f'<text x="{xa_ - 12}" y="{my + 4}" text-anchor="end" font-size="10">{ref} {lab}</text>')
            elif kind == "ecap":
                (xa_, ya_), (xb_, yb_) = pts
                mx = (xa_ + xb_) / 2
                out.append(f'<circle cx="{mx}" cy="{ya_}" r="{P*0.62}" fill="#1f4e8c" stroke="#0d2a50"/>')
                out.append(f'<text x="{xa_ - P*0.05}" y="{ya_ + 4}" text-anchor="middle" font-size="12" fill="#fff" font-weight="bold">+</text>')
                out.append(f'<text x="{mx}" y="{ya_ - P*0.75}" text-anchor="middle" font-size="10">{ref} {lab}</text>')
            elif kind == "fcap":
                (xa_, ya_), (xb_, yb_) = pts
                out.append(f'<rect x="{xa_ - 8}" y="{ya_ - 6}" width="{xb_ - xa_ + 16}" height="12" fill="#c0392b" opacity="0.85"/>')
                out.append(f'<text x="{(xa_ + xb_)/2}" y="{ya_ + 4}" text-anchor="middle" font-size="9" fill="#fff">{ref} {lab}</text>')
            elif kind == "hdr":
                (xa_, ya_) = pts[0]; (xb_, _) = pts[-1]
                out.append(f'<rect x="{xa_ - P*0.45}" y="{ya_ - P*0.45}" width="{xb_ - xa_ + P*0.9}" height="{P*0.9}" fill="#222" opacity="0.85"/>')
                for (x, y), (h, n) in zip(pts, pl):
                    out.append(f'<rect x="{x-3}" y="{y-3}" width="6" height="6" fill="#f1c40f"/>')
            elif kind == "wire":
                (x, y), = pts
                out.append(f'<circle cx="{x}" cy="{y}" r="6" fill="none" stroke="#2a5db0" stroke-width="2.5"/>')
        return
    ox1, oy = 110, 70
    view(ox1, oy, False, "Component side (parts face out)", False)
    ox2 = ox1 + W + 210
    view(ox2, oy, True, "Solder side (mirrored)", True)
    # labels
    lab = []
    y = oy + H + 60
    notes = [
        "Strips run vertically, 12 holes each. A = toward the case front, G = toward the back wall. Row 12 = bottom edge into J3.",
        "✕ = cut the strip (drill the hole): A6, B6, C6, E6 (from the copper side). D stays uncut (+12 V).",
        "Header row 12: A J3.6 GND, B J3.5 (pull pin), C J3.4 +5V (pull pin), D J3.3 +12V, E J3.2 GND, F J3.1 DAC.",
        "T1 pins 2 and 5 (D3, D9) are not connected inside: clipped (strip D is +12 V).",
        "C1 + toward the DAC (B10). R1 lies flat in row 11 from F to B. R2 stands on A, legs in A5 and A7 (across the cut).",
        "C2 = WIMA MKS2 1 µF polyester film, 5 mm pitch (E1-G1), either way round.",
        "JP1 (row 1, A-D): no feed = one jumper B-C (RA-RD). Loop feed = jumpers A-B and C-D. Two caps max on 4 pins, so the two settings cannot mix.",
        "Wires (blue rings): dialer pair = C2 (RD) + G3 (TIP); answerer pair = B3 (RA) + G4 (TIP). JST at the jack-board end.",
    ]
    for i, t in enumerate(notes):
        lab.append(f'<text x="30" y="{y + i*20}" font-size="12">{t}</text>')
    # net legend next to component view
    legend = [("A upper", "R2 / JP1"), ("A lower", "GND"), ("B upper", "RA (answerer)"), ("B lower", "R1-C1 node"),
              ("C upper", "RD (dialer), T1.6"), ("C lower", "T1.1"), ("D", "+12 V"), ("E upper", "T1.4 → C2"),
              ("E lower", "GND, T1.3"), ("F", "DAC GPIO25"), ("G", "TIP (both modems)")]
    lx = ox1 + W + 40
    for i, (a, b) in enumerate(legend):
        lab.append(f'<text x="{lx}" y="{oy + i*17}" font-size="10" fill="#333"><tspan font-weight="bold">{a}</tspan>: {b}</text>')
    width, height = max(ox2 + W + 80, 1060), y + len(notes)*20 + 20
    body = "\n".join(out + lab)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif">\n<rect width="100%" height="100%" fill="#fff"/>\n{body}\n</svg>\n'

if __name__ == "__main__":
    if not check(): sys.exit(1)
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notes", "lineboard.svg")
    open(p, "w").write(svg())
    print("wrote", os.path.normpath(p))
