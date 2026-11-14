#!/usr/bin/env python3
"""Logo bitmap for the lid engraving: cad/logo_xecaz.jpg -> cad/logo_xecaz.pbm (plain P1, 1 = cut) + preview.
Stdlib + ImageMagick `convert` (system). Grid CELL mm per pixel; the case script reads the PBM.
Usage: python3 -I tools/mklogo.py [width_mm] [threshold 0-255] [dilate_cells] [cover 0-1]"""
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "cad", "logo_xecaz.jpg")
OUT = os.path.join(ROOT, "cad", "logo_xecaz.pbm")
PREVIEW = os.path.join(ROOT, "notes", "logo_lid_preview.png")
CELL = 0.2
width_mm = float(sys.argv[1]) if len(sys.argv) > 1 else 113.0
thr = int(sys.argv[2]) if len(sys.argv) > 2 else 90
dil = int(sys.argv[3]) if len(sys.argv) > 3 else 1
cover = float(sys.argv[4]) if len(sys.argv) > 4 else 0.3   # share of lit source pixels that turns a cell on

# brightest channel per pixel (green/white/cyan lines on black), as binary PGM
pgm = subprocess.run(["convert", SRC, "-separate", "-evaluate-sequence", "max", "-depth", "8", "pgm:-"],
                     check=True, capture_output=True).stdout
parts, pos = [], 0
while len(parts) < 4:                       # P5 header: magic, w, h, maxval
    while pgm[pos:pos + 1].isspace():
        pos += 1
    end = pos
    while not pgm[end:end + 1].isspace():
        end += 1
    parts.append(pgm[pos:end]); pos = end
pos += 1
W, H = int(parts[1]), int(parts[2])
px = pgm[pos:pos + W * H]
on = lambda x, y: px[y * W + x] >= thr

xs = [x for y in range(H) for x in range(W) if on(x, y)]
ys = [y for y in range(H) for x in range(W) if on(x, y)]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
mm_per_px = width_mm / (x1 - x0 + 1)
gw = int(round(width_mm / CELL))
gh = int(round((y1 - y0 + 1) * mm_per_px / CELL))
step = (x1 - x0 + 1) / gw
grid = []
for gy in range(gh):
    row = []
    for gx in range(gw):                    # cell is on if enough of its source pixels are lit
        sx0, sx1 = x0 + int(gx * step), x0 + int((gx + 1) * step)
        sy0, sy1 = y0 + int(gy * step), y0 + int((gy + 1) * step)
        cells = [on(x, y) for y in range(sy0, max(sy1, sy0 + 1)) for x in range(sx0, max(sx1, sx0 + 1))]
        row.append(sum(cells) >= cover * len(cells))
    grid.append(row)
for _ in range(dil):                        # thicken: thin lines would not print
    g2 = [[any(grid[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
               if 0 <= y + dy < gh and 0 <= x + dx < gw) for x in range(gw)] for y in range(gh)]
    grid = g2
# cells touching only at a corner make non-manifold edges in the engraving: fill one of the two gaps
fixed = 1
while fixed:
    fixed = 0
    for y in range(gh - 1):
        for x in range(gw - 1):
            a, b, c, d = grid[y][x], grid[y][x + 1], grid[y + 1][x], grid[y + 1][x + 1]
            if a and d and not b and not c:
                grid[y][x + 1] = True
                fixed += 1
            elif b and c and not a and not d:
                grid[y][x] = True
                fixed += 1
with open(OUT, "w") as f:
    f.write(f"P1\n# lid logo, {CELL} mm per cell, {width_mm} mm wide\n{gw} {gh}\n")
    for row in grid:
        f.write("".join("1" if v else "0" for v in row) + "\n")
# preview: dark engraving on the lid colour, 4 px per cell
subprocess.run(["convert", OUT, "+level-colors", "#3a3a3a,#c9c4ba",
                "-scale", "400%", "-bordercolor", "#c9c4ba", "-border", "40", PREVIEW], check=True)
print(f"cover {cover}, {gw} x {gh} cells = {gw * CELL:.1f} x {gh * CELL:.1f} mm, threshold {thr}, dilate {dil}, "
      f"source line ~{mm_per_px:.3f} mm/px -> {OUT}")
