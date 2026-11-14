# Test piece for the heat-set insert bosses (notes/case.md "Fasteners"): M2 x 3 x 3.5 inserts.
# Three bosses as in the case (Ø7, 7 mm tall, hole 4.5 deep) with holes Ø3.3 / Ø3.5 / Ø3.7, marked by
# 1 / 2 / 3 small holes in the plate (Ø3.5 = the case value). Plus a 2.5 mm lid tab with the lid's screw hole
# (Ø3.4 through, Ø5.5 x 1.2 counterbore) to try a screw into a set insert.
# Result 2026-11-12: Ø3.5 boss hole best; lid hole and counterbore +1 mm (were 2.4 / 4.5).
# Run headless:  freecadcmd cad/test_boss.py   (writes cad/test_boss.FCStd, .stl)
import os

import FreeCAD as App
import Mesh
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(os.getcwd(), "cad")
V = App.Vector
T = 2.5
BOSS_D, BOSS_H, DEPTH = 7.0, 7.0, 4.5
HOLES = [3.3, 3.5, 3.7]

piece = Part.makeBox(58, 22, T)
for i, d in enumerate(HOLES):
    x = 9 + i * 14
    piece = piece.fuse(Part.makeCylinder(BOSS_D / 2, BOSS_H, V(x, 9, T - 0.1)))
    piece = piece.cut(Part.makeCylinder(d / 2, DEPTH + 1, V(x, 9, T + BOSS_H - DEPTH)))
    for k in range(i + 1):                                   # marker holes: 1, 2, 3
        piece = piece.cut(Part.makeCylinder(0.75, T + 2, V(x - (i * 1.6) + k * 3.2, 18.5, -1)))
# lid tab with the lid's counterbored screw hole
tx, ty = 51.0, 11.0
piece = piece.cut(Part.makeCylinder(1.7, T + 2, V(tx, ty, -1)))        # v1: Ø2.4 / 4.5, 1 mm too small
piece = piece.cut(Part.makeCylinder(2.75, 2, V(tx, ty, T - 1.2)))
piece = piece.removeSplitter()

doc = App.newDocument("test_boss")
obj = doc.addObject("Part::Feature", "TestBoss")
obj.Shape = piece
doc.recompute()
fc = os.path.join(HERE, "test_boss.FCStd")
if os.path.exists(fc):
    os.remove(fc)
doc.saveAs(fc)
Mesh.export([obj], os.path.join(HERE, "test_boss.stl"))
print(f"test boss: 58 x 22 mm, bosses {HOLES}, valid {piece.isValid()}")
