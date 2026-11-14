# Test plate: every panel cutout of the case in a flat plate, to test-fit the real parts before
# printing the case (notes/case.md, "Measured parts"). Dimensions in mm.
# Run headless:  freecadcmd cad/test_plate.py   (writes cad/test_plate.FCStd, .stl, .svg)
import math
import os

import FreeCAD as App
import Mesh
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "cad")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H, T = 120.0, 44.0, 2.5      # plate; 2.5 mm = planned wall thickness
TEXT_H, ENGRAVE = 3.2, 0.6
V = App.Vector


def prism(points):
    """Closed polygon (x, y) list -> solid through the plate."""
    pts = [V(x, y, -1) for x, y in points] + [V(points[0][0], points[0][1], -1)]
    return Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, T + 2))


def rect(cx, cy, w, h):
    return prism([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
                  (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)])


def hole(cx, cy, d):
    return Part.makeCylinder(d / 2, T + 2, V(cx, cy, -1))


def d_hole(cx, cy, d, flat):
    """Round hole with one flat (fuse holder thread): flat on the right, 'flat' mm across."""
    c = hole(cx, cy, d)
    keep = Part.makeBox(flat, d + 2, T + 4, V(cx - d / 2, cy - d / 2 - 1, -2))
    return c.common(keep)


def db9(cx, cy, top=19.5, h=11.0, angle=10.0, screw_d=3.2, pitch=25.0):
    """DE-9 male D cutout (wide side up) and its two standoff holes."""
    bottom = top - 2 * h * math.tan(math.radians(angle))
    d = prism([(cx - top / 2, cy + h / 2), (cx + top / 2, cy + h / 2),
               (cx + bottom / 2, cy - h / 2), (cx - bottom / 2, cy - h / 2)])
    return d.fuse(hole(cx - pitch / 2, cy, screw_d)).fuse(hole(cx + pitch / 2, cy, screw_d))


def label(text, cx, y):
    """Engraved text centred on cx, baseline at y (top face)."""
    try:
        import Draft
        ss = Draft.make_shapestring(text, FONT, TEXT_H)
        App.ActiveDocument.recompute()
        shp = ss.Shape.copy()
        App.ActiveDocument.removeObject(ss.Name)
    except Exception:
        return None
    bb = shp.BoundBox
    shp.translate(V(cx - (bb.XMin + bb.XMax) / 2, y - bb.YMin, T - ENGRAVE))
    return shp.extrude(V(0, 0, ENGRAVE + 1))


doc = App.newDocument("test_plate")

# v2 (2026-11-12): the sizes confirmed by plate v1 (notes/case.md, "Test plate results"), one row.
# v1 had R1/R2 rocker, F 12.5/11.5, DB9 19.5 x 11 + 3.2, J1/J2, LED 6.5, USB, 3.0/3.2/3.4 (git history).
A = 22.0
features = [
    (rect(11, A, 12.0, 19.9), "R", 11),         # rocker: v1 R2 width, 0.5 lower
    (d_hole(30, A, 13.25, 12.25), "F", 30),     # fuse holder: v1 + 0.75
    (db9(62, A, top=20.5, h=10.0, screw_d=4.2), "DB9", 62),   # v1 + 1 wide, - 1 high; holes + 1
    (rect(91, A, 10.4, 11.4), "J", 91),         # barrel jack flush (v1 J1, perfect)
    (rect(108, A, 12.0, 8.0), "USB", 108),      # micro USB cable (v1 not checked yet)
]

plate = Part.makeBox(W, H, T)
for cut, _, _ in features:
    plate = plate.cut(cut)

# labels: row A under the features, row B under the features
labels_ok = True
for cut, text, cx in features:
    bb = cut.BoundBox
    y = bb.YMin - TEXT_H - 2.0
    lab = label(text, cx, y)
    if lab is None:
        labels_ok = False
        break
    plate = plate.cut(lab)
lab = label("test plate v2  t=2.5", W / 2, H - TEXT_H - 3) if labels_ok else None
if lab is not None:
    plate = plate.cut(lab)

plate = plate.removeSplitter()
obj = doc.addObject("Part::Feature", "TestPlate")
obj.Shape = plate
doc.recompute()

fcstd = os.path.join(HERE, "test_plate.FCStd")
if os.path.exists(fcstd):
    os.remove(fcstd)                     # saveAs over an existing file leaves .FCBak copies
doc.saveAs(fcstd)
Mesh.export([obj], os.path.join(HERE, "test_plate.stl"))

# Top-view SVG of the through-cuts and labels (for a quick check without opening FreeCAD)
paths = []
edges = plate.section(Part.makePlane(W + 20, H + 20, V(-10, -10, T - 0.3))).Edges
for e in edges:
    pts = e.discretize(Deflection=0.05)
    d = "M " + " L ".join(f"{p.x:.2f},{H - p.y:.2f}" for p in pts)
    paths.append(f'<path d="{d}"/>')
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * 6:.0f}" height="{H * 6:.0f}" '
       f'viewBox="-2 -2 {W + 4} {H + 4}"><rect x="-2" y="-2" width="{W + 4}" height="{H + 4}" fill="#fff"/>'
       f'<g fill="none" stroke="#000" stroke-width="0.15">{"".join(paths)}</g></svg>')
with open(os.path.join(HERE, "test_plate.svg"), "w") as f:
    f.write(svg)

print(f"test plate: {W} x {H} x {T} mm, {len(features)} cutouts, labels {'on' if labels_ok else 'OFF (font/Draft failed)'}")
print("volume", round(plate.Volume, 1), "mm3, valid", plate.isValid())
