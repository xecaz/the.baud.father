# Case draft (notes/case.md): base + lid, with stand-in blocks for the parts inside (for the pictures only).
# Run headless:  freecadcmd cad/case.py   -> cad/case.FCStd, case_base.stl, case_lid.stl, notes/case3d_*.png
# Coordinates (mm): x left->right seen from the front, y front (0, faces the Couriers) -> back, z up.
import math
import os
import subprocess

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "cad")
NOTES = os.path.join(HERE, "..", "notes")
V = App.Vector

# --- box ---
L, D, H = 160.0, 110.0, 72.0      # outside, lid included (170 -> 160 on 2026-11-14: right half was empty)
T = 2.5                           # wall, floor and lid
HB = H - T                        # base height (lid plate sits on top)
R_OUT, R_IN = 4.0, 1.5
POST_R, POST_OFF = 4.0, 3.5       # lid screw posts in the inner corners, 0.5 mm into both walls (M2 insert at the top)
INSERT_D, INSERT_DEPTH = 3.5, 9.0      # Ø3.5 won the boss test (2026-11-12: 3.3 / 3.5 / 3.7); 9 mm deep (2026-11-14) so longer screws fit without drilling
LID_HOLE, LID_CB = 3.4, 5.5      # lid screw hole and counterbore (test piece: 2.4 / 4.5 were 1 mm too small)

# --- main board (perfboard 70 x 90, rows along y: row 1 at the back = ESP32 USB end) ---
MB_X0, MB_Y0, MB_W, MB_L = 11.0, 15.0, 70.0, 90.0
MB_Z = T + 7.0                    # on 7 mm bosses
PITCH = 2.54
def col_x(c): return MB_X0 + 3.25 + c * PITCH            # column A=0 .. Z=25
def row_y(r): return MB_Y0 + MB_L - 6.9 - (r - 1) * PITCH  # row 1 .. 31
MB_HOLES = [(MB_X0 + 2.7, MB_Y0 + 3.15), (MB_X0 + 2.7 + 64.6, MB_Y0 + 3.15),
            (MB_X0 + 2.7, MB_Y0 + 3.15 + 83.7), (MB_X0 + 2.7 + 64.6, MB_Y0 + 3.15 + 83.7)]
SOCK_TOP = MB_Z + 1.6 + 8.5       # top of the female headers

# --- panel cutouts (final sizes from the test plates) ---
FRONT = {  # x, z
    "DB9 dialer": (45.0, 50.0), "DB9 answerer": (82.0, 50.0),
    "LINE dialer": (113.15, 19.8), "LINE answerer": (130.85, 19.8),
    "RING": (140.0, 38.0), "LED": (140.0, 58.0),   # 2026-11-14: RING above the line jacks (its nut clears them)
}
BACK = {  # x, z (x is the global x; seen from behind it is mirrored)
    "USB": (col_x(6), SOCK_TOP + 1.6 + 1.5 + 3.0), "power switch": (96.0, 40.0),   # USB +3 mm (print 1: too low)
    "12 V in": (115.0, 12.0), "fuse": (135.0, 32.0),
}
RING_HOLE = 12.0                  # scrap pushbutton (2026-11-12): needs 12 mm; Ø12.5 (test plate v1) fitted, file if snug


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def rbox(x0, y0, z0, dx, dy, dz, r):
    b = box(x0, y0, z0, dx, dy, dz)
    edges = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return b.makeFillet(r, edges)


def cyl(x, y, z, r, h, d=V(0, 0, 1)):
    return Part.makeCylinder(r, h, V(x, y, z), d)


def wall_prism(pts, y0, y1):
    """Polygon (x, z) in a front/back wall, extruded from y0 to y1."""
    vs = [V(a, y0, b) for a, b in pts] + [V(pts[0][0], y0, pts[0][1])]
    return Part.Face(Part.makePolygon(vs)).extrude(V(0, y1 - y0, 0))


def wall_rect(cx, cz, w, h, y0, y1):
    return wall_prism([(cx - w / 2, cz - h / 2), (cx + w / 2, cz - h / 2), (cx + w / 2, cz + h / 2), (cx - w / 2, cz + h / 2)], y0, y1)


def wall_hole(cx, cz, d, y0, y1):
    return cyl(cx, y0, cz, d / 2, y1 - y0, V(0, 1, 0))


def db9_cut(cx, cz):
    top, h = 20.5, 10.0
    bot = top - 2 * h * math.tan(math.radians(10))
    d = wall_prism([(cx - top / 2, cz + h / 2), (cx + top / 2, cz + h / 2), (cx + bot / 2, cz - h / 2), (cx - bot / 2, cz - h / 2)], -1, T + 1)
    for dx in (-12.5, 12.5):
        d = d.fuse(wall_hole(cx + dx, cz, 4.2, -1, T + 1))
    return d.fuse(wall_rect(cx, cz, 34, 15, 0.9, T + 0.5))   # pocket: wall 0.9 mm under the flange (short screws)


def fuse_cut(cx, cz):
    d, flat = 13.25, 12.25
    c = wall_hole(cx, cz, d, D - T - 1, D + 1)
    return c.common(box(cx - d / 2, D - T - 2, cz - d / 2 - 1, flat, T + 4, d + 2))


# ---------------- base ----------------
base = rbox(0, 0, 0, L, D, HB, R_OUT).cut(rbox(T, T, T, L - 2 * T, D - 2 * T, HB, R_IN))
posts = [(T + POST_OFF, T + POST_OFF), (L - T - POST_OFF, T + POST_OFF),
         (T + POST_OFF, D - T - POST_OFF), (L - T - POST_OFF, D - T - POST_OFF)]
for px, py in posts:
    base = base.fuse(cyl(px, py, T - 0.1, POST_R, HB - T + 0.1))   # touches both walls
for hx, hy in MB_HOLES:                                       # main board bosses
    base = base.fuse(cyl(hx, hy, T - 0.1, 3.5, 7.1))
BUCK = (108.0, 45.0, 43.0, 21.0)                              # x0, y0, w, d
bcx, bcy = BUCK[0] + BUCK[2] / 2, BUCK[1] + BUCK[3] / 2
BUCK_HOLES = [(bcx - 14.9, bcy + 7.5), (bcx + 14.9, bcy - 7.5)]   # 33.4 mm diagonal (print 1 had it mirrored); drill the pads in place
BUCK_PAD_R, BUCK_PAD_H = 3.5, 7.6                             # Ø7 bosses with inserts, like the main board (2026-11-14)
for hx, hy in BUCK_HOLES:
    base = base.fuse(cyl(hx, hy, T - 0.1, BUCK_PAD_R, BUCK_PAD_H + 0.1))
RJB = (100.0, 5.0, 45.0, 30.0)                                # line jack board (stand-in size), 10 mm above the floor
# one ledge under the front strip of the jack board, as wide as the jack pair: the board is hot-glued (user,
# 2026-11-12), so its cut size does not matter
base = base.fuse(box(105.0, 6.0, T - 0.1, 34.0, 6.0, 10.1))
bx, bz = BACK["12 V in"]                                      # barrel jack cradle
base = base.fuse(box(bx - 7, D - T - 15, T - 0.1, 14, 15, bz - 5.5 - T + 0.1))
base = base.fuse(box(bx - 7, D - T - 15, T - 0.1, 2, 15, bz - T)).fuse(box(bx + 5, D - T - 15, T - 0.1, 2, 15, bz - T))

cuts = []
for name, (x, z) in FRONT.items():
    if name.startswith("DB9"):
        cuts.append(db9_cut(x, z))
    elif name.startswith("LINE"):
        cuts.append(wall_rect(x, z, 14.5, 11.7, -1, T + 1))
    elif name == "LED":
        cuts.append(wall_hole(x, z, 6.5, -1, T + 1))
    elif name == "RING":
        cuts.append(wall_hole(x, z, RING_HOLE, -1, T + 1))
for name, (x, z) in BACK.items():
    if name == "USB":
        cuts.append(wall_rect(x, z, 12.0, 8.0, D - T - 1, D + 1))
    elif name == "power switch":
        cuts.append(wall_rect(x, z, 12.0, 19.9, D - T - 1, D + 1))
    elif name == "12 V in":
        cuts.append(wall_rect(x, z, 10.4, 11.4, D - T - 1, D + 1))
    elif name == "fuse":
        cuts.append(fuse_cut(x, z))
for px, py in posts:
    cuts.append(cyl(px, py, HB - INSERT_DEPTH, INSERT_D / 2, INSERT_DEPTH + 1))
for hx, hy in MB_HOLES:
    cuts.append(cyl(hx, hy, T + 7 - INSERT_DEPTH, INSERT_D / 2, INSERT_DEPTH + 1))
for hx, hy in BUCK_HOLES:
    cuts.append(cyl(hx, hy, T + BUCK_PAD_H - INSERT_DEPTH, INSERT_D / 2, INSERT_DEPTH + 1))
for c in cuts:
    base = base.cut(c)
base = base.removeSplitter()

# ---------------- lid ----------------
lid = rbox(0, 0, HB, L, D, T, R_OUT)
CL, LIP_T, LIP_H = 0.3, 1.5, 4.0
lip = box(T + CL, T + CL, HB - LIP_H, L - 2 * (T + CL), D - 2 * (T + CL), LIP_H + 0.1).cut(
    box(T + CL + LIP_T, T + CL + LIP_T, HB - LIP_H - 1, L - 2 * (T + CL + LIP_T), D - 2 * (T + CL + LIP_T), LIP_H + 2))
for px, py in posts:
    lip = lip.cut(box(px - 8, py - 8, HB - LIP_H - 1, 16, 16, LIP_H + 1))
lid = lid.fuse(lip)
for px, py in posts:
    lid = lid.cut(cyl(px, py, HB - 1, LID_HOLE / 2, T + 2)).cut(cyl(px, py, H - 1.2, LID_CB / 2, 2))

# logo engraved into the lid top (user's logo, cad/logo_xecaz.jpg -> tools/mklogo.py -> cad/logo_xecaz.pbm):
# 2/3 of the lid width, centred; text reads from the front edge. The lid prints top face down, so the
# engraving is on the bed side (clean edges).
LOGO_PBM, LOGO_DEPTH, LOGO_CELL = os.path.join(HERE, "logo_xecaz.pbm"), 0.6, 0.2


def logo_cutter(cx, cy, ztop):
    with open(LOGO_PBM) as f:
        toks = [t for line in f if not line.startswith("#") for t in line.split()]
    gw, gh = int(toks[1]), int(toks[2])
    bits = "".join(toks[3:])
    runs = {}                                          # (x0, x1) -> list of rows, merged vertically below
    for r in range(gh):
        row = bits[r * gw:(r + 1) * gw]
        c = 0
        while c < gw:
            if row[c] == "1":
                c0 = c
                while c < gw and row[c] == "1":
                    c += 1
                runs.setdefault((c0, c), []).append(r)
            else:
                c += 1
    boxes = []
    for (c0, c1), rows in runs.items():
        start = prev = rows[0]
        for r in rows[1:] + [None]:
            if r is not None and r == prev + 1:
                prev = r
                continue
            x = cx + (c0 - gw / 2) * LOGO_CELL
            y = cy + (gh / 2 - prev - 1) * LOGO_CELL
            boxes.append(box(x, y, ztop - LOGO_DEPTH, (c1 - c0) * LOGO_CELL, (prev - start + 1) * LOGO_CELL, LOGO_DEPTH + 1))
            if r is not None:
                start = prev = r
    return Part.makeCompound(boxes), len(boxes), gw * LOGO_CELL, gh * LOGO_CELL


if os.path.exists(LOGO_PBM):
    cutter, n, lw, lh = logo_cutter(L / 2, D / 2, H)
    lid = lid.cut(cutter)
    print(f"logo: {lw:.1f} x {lh:.1f} mm, {n} boxes, {LOGO_DEPTH} mm deep")
lid = lid.removeSplitter()

# ---------------- stand-ins for the parts (pictures only) ----------------
parts = []   # (name, shape, colour)
def part(name, shp, colour): parts.append((name, shp, colour))
part("main board", box(MB_X0, MB_Y0, MB_Z, MB_W, MB_L, 1.6), "#2e8b57")
for c in (1, 11):
    part("ESP32 headers", box(col_x(c) - 1.27, row_y(20) - 1.27, MB_Z + 1.6, 2.54, row_y(2) - row_y(20) + 2.54, 8.5), "#222")
ex = col_x(6)
part("ESP32", box(ex - 14.1, row_y(2) + 4 - 55, SOCK_TOP, 28.2, 55, 1.6), "#1a1a1a")
part("ESP32 module", box(ex - 9, row_y(2) + 4 - 55, SOCK_TOP + 1.6, 18, 25.5, 3.2), "#c8c8c8")
part("ESP32 USB", box(ex - 3.75, row_y(2) + 4 - 5.5, SOCK_TOP + 1.6, 7.5, 5.6, 2.6), "#bbb")
for r0, nm in ((3, "carrier 1 (dialer)"), (12, "carrier 2 (answerer)")):
    y1, y0 = row_y(r0) + 1.27, row_y(r0 + 5) - 1.27
    cx = col_x(15)
    part(nm + " socket", box(cx - 1.27, y0, MB_Z + 1.6, 2.54, y1 - y0, 8.5), "#222")
    part(nm, box(cx - 0.8, (y0 + y1) / 2 - 8.75, SOCK_TOP, 1.6, 17.5, 40), "#d9b77c")
    part(nm + " MAX3232", box(cx + 0.8, (y0 + y1) / 2 - 7.5, SOCK_TOP + 12, 9, 15, 25), "#2b4c9b")
zx = col_x(25)
part("line board socket", box(zx - 1.27, row_y(8) - 1.27, MB_Z + 1.6, 2.54, row_y(3) - row_y(8) + 2.54, 8.5), "#222")
part("line board", box(zx - 0.8, row_y(8) - 1.27, SOCK_TOP, 1.6, row_y(2) - row_y(8) + 2.54, 30.5), "#d9b77c")   # 7 strips x 12 holes
part("SM-LP-5001", box(zx + 0.8, MB_Y0 + 50, SOCK_TOP + 6, 12, 20, 15), "#333")
part("JST row", box(col_x(15) - 1.27, row_y(30) - 3, MB_Z + 1.6, col_x(24) - col_x(15) + 2.54, 6, 7), "#eee")
part("C1 470 uF", cyl(col_x(14), row_y(20.5), MB_Z + 1.6, 4, 12), "#1f3f7f")
part("LM2596", box(BUCK[0], BUCK[1], T + 7.5, BUCK[2], BUCK[3], 1.6), "#2850a0")
part("LM2596 coil", box(BUCK[0] + 4, BUCK[1] + 4, T + 9.1, 12, 12, 7), "#444")
part("line jack board", box(RJB[0], RJB[1], T + 10, RJB[2], RJB[3], 1.6), "#3a7d44")
for nm in ("LINE dialer", "LINE answerer"):
    x, z = FRONT[nm]
    part(nm, box(x - 6.55, T + 0.5, z - 5.65, 13.1, 15, 11.3), "#555")
for nm in ("DB9 dialer", "DB9 answerer"):
    x, z = FRONT[nm]
    part(nm + " flange", box(x - 16, 0.9, z - 6.5, 32, 1, 13), "#aaa")
    part(nm, box(x - 10, 1.9, z - 5, 20, 8, 10), "#222")
    part(nm + " shell", wall_prism([(x - 8.5, z + 4), (x + 8.5, z + 4), (x + 7, z - 4), (x - 7, z - 4)], -6, 0.9), "#bbb")
    for dx in (-12.5, 12.5):
        hexa = [V(x + dx + 2.5 * math.cos(a * math.pi / 3), 0, z + 2.5 * math.sin(a * math.pi / 3)) for a in range(7)]
        part(nm + " standoff", Part.Face(Part.makePolygon(hexa)).extrude(V(0, -5, 0)), "#bbb")
x, z = FRONT["LED"]
part("LED", cyl(x, 1.0, z, 2.5, 6, V(0, -1, 0)).fuse(Part.makeSphere(2.5, V(x, -5, z))), "#3cb043")
x, z = FRONT["RING"]
part("RING button", cyl(x, 0, z, 6, 5, V(0, -1, 0)), "#c0392b")
part("RING button body", cyl(x, T, z, 6, 18, V(0, 1, 0)), "#333")
x, z = BACK["fuse"]
part("fuse cap", cyl(x, D, z, 7.5, 12, V(0, 1, 0)), "#222")
part("fuse body", cyl(x, D - T - 28, z, 6.15, 28, V(0, 1, 0)), "#222")
part("fuse nut", cyl(x, D - T - 3, z, 8, 3, V(0, 1, 0)), "#888")
x, z = BACK["12 V in"]
part("barrel jack", box(x - 5, D - T - 14 + 0.3, z - 5.5, 10, 14, 11), "#222")
x, z = BACK["power switch"]
part("switch bezel", box(x - 7.5, D, z - 11, 15, 2.5, 22), "#222")
part("switch rocker", box(x - 5, D + 2.5, z - 8.5, 10, 2, 17).fuse(box(x - 5, D + 2.5, z, 10, 3.5, 8.5)), "#b22")
part("switch body", box(x - 5.8, D - T - 20, z - 10, 11.6, 20, 20), "#222")

# ---------------- save ----------------
doc = App.newDocument("case")
for nm, shp in (("Base", base), ("Lid", lid)):
    o = doc.addObject("Part::Feature", nm)
    o.Shape = shp
grp = doc.addObject("App::DocumentObjectGroup", "StandIns")
for i, (nm, shp, _) in enumerate(parts):
    o = doc.addObject("Part::Feature", f"P{i:02d}")
    o.Label = nm
    o.Shape = shp
    grp.addObject(o)
doc.recompute()
fc = os.path.join(HERE, "case.FCStd")
if os.path.exists(fc):
    os.remove(fc)
doc.saveAs(fc)
import Mesh
Mesh.export([doc.getObject("Base")], os.path.join(HERE, "case_base.stl"))      # prints as is, open side up
lid_print = lid.copy()
lid_print.rotate(V(0, 0, 0), V(1, 0, 0), 180)                                   # top face down on the bed
lid_print.translate(V(0, 0, -lid_print.BoundBox.ZMin))
o = doc.addObject("Part::Feature", "LidPrint")
o.Shape = lid_print
Mesh.export([o], os.path.join(HERE, "case_lid.stl"))
doc.removeObject("LidPrint")
print(f"case {L} x {D} x {H}: base valid {base.isValid()}, lid valid {lid.isValid()}, inner height {HB - T:.1f}")
print("tallest part top:", round(max(s.BoundBox.ZMax for n, s, _ in parts if not n.startswith(('switch', 'fuse', 'LED', 'RING'))), 1), "lid underside", HB, "lip bottom", HB - LIP_H)


# ---------------- shaded views (painter's algorithm into SVG) ----------------
def tris_of(shape, tol=0.25, maxlen=6.0):
    pts, tris = shape.tessellate(tol)
    out = []
    def split(a, b, c, depth=0):
        la, lb, lc = (b - c).Length, (a - c).Length, (a - b).Length
        m = max(la, lb, lc)
        if m <= maxlen or depth > 6:
            out.append((a, b, c))
            return
        if m == la:
            mid = (b + c) * 0.5; split(a, b, mid, depth + 1); split(a, mid, c, depth + 1)
        elif m == lb:
            mid = (a + c) * 0.5; split(a, b, mid, depth + 1); split(mid, b, c, depth + 1)
        else:
            mid = (a + b) * 0.5; split(a, mid, c, depth + 1); split(mid, b, c, depth + 1)
    for i, j, k in tris:
        split(pts[i], pts[j], pts[k])
    return out


CACHE = {}
def mesh(key, shape):
    if key not in CACHE:
        CACHE[key] = tris_of(shape)
    return CACHE[key]


def shade(hexc, f):
    if len(hexc) == 4:
        hexc = "#" + "".join(ch * 2 for ch in hexc[1:])
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * f))) for v in (r, g, b))


def view(items, az, el, scale, labels=(), title=""):
    """items: (key, shape, colour). Returns (svg body, width, height)."""
    a, e = math.radians(az), math.radians(el)
    cam = V(math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))
    right = V(-math.sin(a), math.cos(a), 0)
    if el < 89.9:
        up = V(-math.sin(e) * math.cos(a), -math.sin(e) * math.sin(a), math.cos(e))
    else:
        up = V(-math.cos(a), -math.sin(a), 0)
    light = V(-0.4, -0.7, 0.9); light.normalize()
    polys = []
    for key, shp, col in items:
        for p, q, r in mesh(key, shp):
            n = (q - p).cross(r - p)
            if n.Length < 1e-9:
                continue
            n.normalize()
            if n.dot(cam) <= 0:
                continue
            f = 0.45 + 0.6 * max(0.0, n.dot(light))
            depth = ((p + q + r) * (1 / 3)).dot(cam)
            polys.append((depth, [(v.dot(right), -v.dot(up)) for v in (p, q, r)], shade(col, f)))
    polys.sort(key=lambda t: t[0])
    xs = [x for _, pp, _ in polys for x, _ in pp]
    ys = [y for _, pp, _ in polys for _, y in pp]
    x0, y0 = min(xs), min(ys)
    pad = 30
    w = (max(xs) - x0) * scale + 2 * pad
    h = (max(ys) - y0) * scale + 2 * pad + 24
    def P(x, y): return ((x - x0) * scale + pad, (y - y0) * scale + pad + 24)
    out = [f'<text x="{pad}" y="20" font-size="17" font-weight="bold">{title}</text>']
    for _, pp, c in polys:
        s = " ".join("%.1f,%.1f" % P(x, y) for x, y in pp)
        out.append(f'<polygon points="{s}" fill="{c}" stroke="{c}" stroke-width="0.6" stroke-linejoin="round"/>')
    for text, pt, (dx, dy) in labels:
        sx, sy = P(pt.dot(right), -pt.dot(up))
        tx, ty = sx + dx, sy + dy
        out.append(f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{tx:.1f}" y2="{ty:.1f}" stroke="#c0392b" stroke-width="1.2"/>'
                   f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="2.5" fill="#c0392b"/>')
        anchor = "end" if dx < 0 else "start"
        out.append(f'<text x="{tx + (-4 if dx < 0 else 4):.1f}" y="{ty + 5:.1f}" font-size="14" text-anchor="{anchor}" '
                   f'stroke="#fff" stroke-width="4" paint-order="stroke">{text}</text>')
    return "\n".join(out), w, h


def sheet(name, views, caption):
    """views: list of (body, w, h) laid out left to right."""
    W = sum(v[1] for v in views) + 20 * (len(views) - 1) + 40
    Hh = max(v[2] for v in views) + 40 + 22 * len(caption)
    body, x = [], 20
    for b, w, h in views:
        body.append(f'<g transform="translate({x:.0f},20)">{b}</g>')
        x += w + 20
    y = max(v[2] for v in views) + 50
    for line in caption:
        body.append(f'<text x="20" y="{y}" font-size="14" fill="#333">{line}</text>')
        y += 22
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{Hh:.0f}" font-family="DejaVu Sans, sans-serif">'
           f'<rect width="100%" height="100%" fill="#fff"/>{"".join(body)}</svg>')
    p = os.path.join(NOTES, name + ".svg")
    with open(p, "w") as f:
        f.write(svg)
    subprocess.run(["rsvg-convert", "-b", "white", "-o", os.path.join(NOTES, name + ".png"), p], check=True)
    os.remove(p)
    print("wrote notes/" + name + ".png")


CASE_COL, LID_COL = "#d8d4cc", "#c9c4ba"
outside = [(n + str(i), s, c) for i, (n, s, c) in enumerate(parts)
           if n.endswith(("shell", "standoff", "cap", "bezel", "rocker")) or n in ("LED", "RING button")]
inside = [(n + str(i), s, c) for i, (n, s, c) in enumerate(parts)]
closed = [("base", base, CASE_COL), ("lid", lid, LID_COL)] + outside
opened = [("base", base, CASE_COL)] + inside

def pt(x, y, z): return V(x, y, z)
F = FRONT; B = BACK
lab_front = [("DB9 dialer", pt(F["DB9 dialer"][0], -6, F["DB9 dialer"][1] + 5), (-40, -60)),
             ("DB9 answerer", pt(F["DB9 answerer"][0], -6, F["DB9 answerer"][1] + 5), (10, -75)),
             ("LINE dialer / answerer", pt(122, 0, 26), (40, 90)),
             ("LED", pt(F["LED"][0], -8, F["LED"][1]), (40, -50)),
             ("RING", pt(F["RING"][0], -5, F["RING"][1]), (50, 30))]
lab_back = [("USB (ESP32)", pt(B["USB"][0], D, B["USB"][1]), (-30, 70)),
            ("power switch", pt(B["power switch"][0], D + 4, B["power switch"][1] + 9), (-20, -70)),
            ("12 V in", pt(B["12 V in"][0], D, B["12 V in"][1]), (30, 70)),
            ("fuse", pt(B["fuse"][0], D + 12, B["fuse"][1]), (40, -60))]
sheet("case3d_outside", [view(closed, -62, 26, 3.2, lab_front, "Front (faces the Couriers)"),
                         view(closed, 118, 26, 3.2, lab_back, "Back")],
      [f"Draft: {L:.0f} x {D:.0f} x {H:.0f} mm outside, 2.5 mm walls, lid with 4 M2 screws into heat-set inserts in the corner posts.",
       "Front: 2x DB9 male (wall thinned to 0.9 mm under the flange), 2x line jack, LED, RING button (Ø12). Back: USB slot, power switch, 12 V barrel jack, fuse."])

lab_in = [("ESP32 (antenna end away from the DB9s)", pt(ex, row_y(20), SOCK_TOP + 3), (30, 160)),
          ("carriers (stand in J1/J2)", pt(col_x(15), row_y(10), SOCK_TOP + 40), (-80, -70)),
          ("line board + SM-LP-5001", pt(zx + 6, row_y(5), SOCK_TOP + 20), (40, -110)),
          ("LM2596 on 2 pads", pt(bcx, bcy, T + 10), (80, -40)),
          ("line jack board on 10 mm ledges", pt(RJB[0] + 20, RJB[1] + 20, T + 12), (60, 60)),
          ("main board on 4 bosses", pt(MB_X0 + 60, MB_Y0 + 5, MB_Z + 1.6), (60, 130))]
lab_top = [("J1 dialer", pt(col_x(15) + 5, row_y(5.5), 60), (-90, 0)),
           ("J2 answerer", pt(col_x(15) + 5, row_y(14.5), 60), (-90, 0)),
           ("ESP32", pt(ex, row_y(14), 30), (-90, 40)),
           ("USB", pt(ex, D, 25), (-60, 20)),
           ("fuse", pt(B["fuse"][0], D - 15, 40), (60, 30)),
           ("barrel", pt(B["12 V in"][0], D - 8, 20), (30, 60)),
           ("switch", pt(B["power switch"][0], D - 10, 50), (50, -30)),
           ("LM2596", pt(bcx, bcy, 20), (90, 0)),
           ("line jacks", pt(122, 15, 25), (90, 30)),
           ("RING", pt(F["RING"][0], 10, 30), (40, -20)),
           ("DB9s", pt(64, 5, 50), (0, -40)),
           ("line board", pt(zx, row_y(5), SOCK_TOP + 20), (40, 60))]
sheet("case3d_inside", [view(opened, -62, 48, 3.2, lab_in, "Inside, lid off"),
                        view(opened, -90, 90, 3.0, lab_top, "Top view (front edge at the bottom)")],
      ["Main board as built: ESP32 USB end at the back wall, carriers in the middle (ribbons up and forward to the DB9s), line board along its right edge.",
       "Right half: line jack board (front, low), LM2596 (middle), barrel jack, fuse and switch on the back wall. Corner posts take the lid screws."])
