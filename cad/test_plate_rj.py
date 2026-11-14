# Test plate for the salvaged line-jack pair (notes/case.md): two 6P4C jacks, 13.1 W x 11.3 H, centres 17.7 mm.
# v1 (2026-11-12): row A +0.4 (13.5 x 11.7) closest, but each jack needed 0.5 mm more on both sides.
# v2: one pair 14.5 x 11.7 (divider 17.7 - 14.5 = 3.2 mm).
# Run headless:  freecadcmd cad/test_plate_rj.py   (writes cad/test_plate_rj.FCStd, .stl, .svg)
import os

import FreeCAD as App
import Mesh
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "cad")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, T = 48.0, 30.0, 2.5
TEXT_H, ENGRAVE = 3.2, 0.6
PITCH = 17.7
V = App.Vector


def rect(cx, cy, w, h):
    return Part.makeBox(w, h, T + 2, V(cx - w / 2, cy - h / 2, -1))


def label(text, cx, y):
    import Draft
    ss = Draft.make_shapestring(text, FONT, TEXT_H)
    App.ActiveDocument.recompute()
    shp = ss.Shape.copy()
    App.ActiveDocument.removeObject(ss.Name)
    bb = shp.BoundBox
    shp.translate(V(cx - (bb.XMin + bb.XMax) / 2, y - bb.YMin, T - ENGRAVE))
    return shp.extrude(V(0, 0, ENGRAVE + 1))


doc = App.newDocument("test_plate_rj")
plate = Part.makeBox(W, H, T)
rows = [(12.5, 14.5, 11.7, "RJ v2 14.5")]
cx0 = W / 2
for cy, w, h, name in rows:
    for dx in (-PITCH / 2, PITCH / 2):
        plate = plate.cut(rect(cx0 + dx, cy, w, h))
    plate = plate.cut(label(name, cx0, cy + h / 2 + 1.2))
plate = plate.removeSplitter()

obj = doc.addObject("Part::Feature", "TestPlateRJ")
obj.Shape = plate
doc.recompute()
fcstd = os.path.join(HERE, "test_plate_rj.FCStd")
if os.path.exists(fcstd):
    os.remove(fcstd)
doc.saveAs(fcstd)
Mesh.export([obj], os.path.join(HERE, "test_plate_rj.stl"))

paths = []
for e in plate.section(Part.makePlane(W + 20, H + 20, V(-10, -10, T - 0.3))).Edges:
    pts = e.discretize(Deflection=0.05)
    paths.append('<path d="M ' + " L ".join(f"{p.x:.2f},{H - p.y:.2f}" for p in pts) + '"/>')
with open(os.path.join(HERE, "test_plate_rj.svg"), "w") as f:
    f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * 8:.0f}" height="{H * 8:.0f}" viewBox="-2 -2 {W + 4} {H + 4}">'
            f'<rect x="-2" y="-2" width="{W + 4}" height="{H + 4}" fill="#fff"/>'
            f'<g fill="none" stroke="#000" stroke-width="0.15">{"".join(paths)}</g></svg>')
print(f"test plate RJ: {W} x {H} x {T} mm, valid {plate.isValid()}")
