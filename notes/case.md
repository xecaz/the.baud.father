# Case (draft 2026-11-05)

Picture: `case.svg` (source) / `case.png` (`rsvg-convert -b white -o case.png case.svg`). Keep in sync.

## Enclosure
- About 160 × 100 × **~70 mm** external (height raised from 50 on 2026-11-12: the MAX3232 carriers and the line
  board stand upright in sockets on the main board, ~45 mm + socket + board + standoffs). **3D printed** (decided 2026-11-06), modelled in FreeCAD.
- **Not metal**: the ESP32 DevKit uses a PCB antenna. Point the antenna end into the box, away from DB9 shells.
- Nothing runs hot (ESP32 + two MAX3232 + a small buck): no vents.
- Keep ~10 mm clear in the corners for screw bosses.

## Panel parts

| Panel | Part | x (mm from left, seen from outside) | Cutout (check the real part) |
|---|---|---|---|
| Front | Power rocker (KCD1 type) | 20 | 19 × 13 mm |
| Front | Status LED in holder | 38 | Ø6–8 mm |
| Front | RING test button (momentary) | 55 | Ø12 mm |
| Front | RJ11 keystone, LINE dialer | 85 | ≈ 15 × 20 mm |
| Front | RJ11 keystone, LINE answerer | 105 | ≈ 15 × 20 mm |
| Front | USB slot to DevKit (**micro USB**; or panel extension, micro USB male inside) | 136 | 12 × 7 mm |
| Rear | 12 V DC barrel jack, 5.5/2.1, centre + | 15 | Ø8 mm (some Ø11) |
| Rear | Fuse holder 5×20, T500 mA | 32 | Ø12.5 mm |
| Rear | DB9 male, ANSWERER | 70 | ≈ 20 × 11 D, holes Ø3.2 at 25 mm |
| Rear | DB9 male, DIALER | 115 | ≈ 20 × 11 D, holes Ø3.2 at 25 mm |

All cutouts centred at half height. The rear panel is drawn from outside, so it is mirrored relative
to the top view.

Beyond the original list (switch, 2× DB9, barrel, fuse) the box also needs:
- **2× RJ11** for the two modems' LINE jacks, since the loop feed and the dial-tone transformer are inside.
- **USB access** to flash the ESP32 without opening the box.
- Optional but cheap: **status LED** and a **RING** button wired to GPIO4 (to GND, internal pull-up) for testing without the phone. Not GPIO0: it is a strapping pin, a held button at power-on would boot into download mode.

## Measured parts (2026-11-12, user's measurements; open questions marked ?)

| # | Part | Measured | Still needed |
|---|---|---|---|
| 1 | Rocker (snap-in, the ordered ones; bigger than the listing's 15 × 10 mm) | 11.6 × 20.0 mm | treated as the body size: cutout 11.8 × 20.2 mm, check on the test plate (below); clip gap and depth behind the panel |
| 2 | Fuse holder 5×20, panel, threaded | thread Ø12.3 mm with one flat: 11.4 mm across (**D-hole** Ø12.5, flat at 11.5); 30.4 mm long; front cap Ø15 mm (needs Ø16 clear space on the outside) | nut Ø; usable thread length (max panel thickness) |
| 3 | Barrel jack, salvaged PCB-mount | body 10.0 W × 11.0 H × 14.0 D mm; plug centre 7.0 mm above the PCB face; centre pin to sleeve pin 6 mm; flat pins 2.6 mm wide | gets a printed cradle (was soldered to a PCB) |
| 4 | Status LED | standard 5 mm LED, no holder: **Ø6.5 mm hole** + rubber gasket | — |
| 5 | RING button | not found yet; hole can be drilled to fit later | thread Ø, depth |
| 6 | DB9 male (on the carrier ribbons) | flange 32 × 13 mm; D-shell 18 mm wide at its widest; **threaded hex standoffs** (usually 4-40 UNC, some M3); screws 25 mm centre to centre | cutout ≈ 19.5 × 11 mm D (or rounded rectangle), 2× Ø3.2 holes at 25 mm: the standoffs unscrew, the wall goes between flange and hex, so the wall at the DB9s ≤ the standoff thread length (usually ~3–4 mm) |
| 7 | ESP32 DevKit (38-pin) | PCB 47.4 × 28.2 mm, **55 mm long including the antenna overhang**; micro USB centred on the 28.2 mm end; pins 8 mm below the PCB; ~5 mm above it at the tallest; **no mounting holes** (sits in female headers on the main board) | keep the antenna end free of metal, a few mm clear |
| 8 | MAX3232 carrier (×2) | 40 × 17.5 mm stripboard, ~47 mm long incl. the bent header pins; 11 mm high | — |
| 9 | LM2596 buck module | 43 × 21 × 15 mm (tallest part); 2 holes ~Ø3 mm at diagonal corners (opposite long sides), 33.4 mm apart diagonally | **user's choice:** two solid Ø12 mm pads, 7–8 mm high, under the holes; drilled in place for heat-set inserts (the pad size absorbs the position tolerance) |
| — | SM-LP-5001 | from the datasheet: 6 legs, rows ~15 mm apart | — |
| — | RJ12 (6P6C) breakout boards ×2 (listing "Sellsum-178-1", arriving 2026-11-12) | from the listing only: jack 14 W × 15 H mm on a ~30 × 22 mm PCB, opening sideways with the PCB flat; 6-pin right-angle header (line = pins 3–4); 2 mounting holes; a scored strip on one side | real jack face (wall cutout), jack overhang past the PCB edge, hole spacing/Ø and position, jack height; which header pins carry the centre pair. Plan: PCB screwed to 2 bosses, jack face in a wall cutout (hot glue as fallback) |
| — | **Line jacks, salvaged (2026-11-12, used until the RJ12 boards arrive, maybe for good)** | two 6P4C jacks on the old DSL modem board (pins 2–5 fitted; line = positions 3 and 4 = the middle two of the four, check with a cord + meter; a 2-pin JST per jack to the line board, polarity free); each 13.1 W × 11.3 H mm, 4.6 mm apart (centres 17.7 mm); fronts stick out ~2 mm past the PCB edge | RJ plate v1: 13.5 × 11.7 closest but tight, needs 0.5 mm more on each side → **14.5 × 11.7** each, centres 17.7 (divider 3.2): **plate v2 fits snug, final (2026-11-12)** (`cad/test_plate_rj.py`); **10 mm free under its PCB** (user: wires soldered underneath + glue), so the jack board sits on a ledge/standoffs ≥ 10 mm above the inner floor: cutout centres ≈ floor + 10 + 1.6 (PCB) + 5.65 (half the 11.3 jack) ≈ **17.3 mm** above the inner floor; fronts ~0.5 mm under the 2.5 mm wall (thin to 2 mm if wanted); board cut down? size and mounting (holes / hot glue) |
| — | Couriers' rear panels | not here | spacing of DB25 / LINE / power |

**Test plate first:** before the full case, print a flat 2–3 mm plate with every panel cutout (rocker,
fuse D-hole, LED Ø6.5, DB9 with its two holes, barrel-jack window) and test-fit the real parts. Cheap,
and it settles the rocker question and the printer's hole shrinkage (holes usually print 0.2–0.4 mm small).
Model: `cad/test_plate.py` (run `freecadcmd cad/test_plate.py` → `test_plate.FCStd`, `.stl`, `.svg` top view).
112 × 72 × 2.5 mm, engraved labels: R1/R2 rocker (11.8 × 20.2 / 12.0 × 20.4), F fuse D-hole (Ø12.5, flat 11.5),
DB9 (D 19.5 × 11 + Ø3.2 at 25 mm), J1 barrel jack window 10.4 × 11.4 (jack flush in the wall), J2 Ø8 (jack
behind the wall), L Ø6.5 LED + gasket, USB 12 × 8 slot, 3.0/3.2/3.4 holes (printer shrinkage). RJ jacks and the
RING button are not on it: drilled and hot-glued after printing (user, 2026-11-12).

**Test plate results (printed 2026-11-12, t = 2.5 mm) → cutouts for the case model:**

| Part | Plate v1 | Fit | **Use in the case** |
|---|---|---|---|
| Rocker | R2 12.0 × 20.4 | width perfect, a bit loose top to bottom | **12.0 × 19.9** |
| Fuse holder | D Ø12.5, flat 11.5 | too tight, needs +0.75 | **D Ø13.25, flat 12.25** |
| DB9 shell | D 19.5 × 11 | needs 1 mm wider, 1 mm lower | **D 20.5 × 10** (10° sides) |
| DB9 standoff holes | Ø3.2 at 25 | the screw thread cut into the plastic | **Ø4.2** at 25 |
| Barrel jack | J1 10.4 × 11.4 | perfect, jack sits flush with the outside | **10.4 × 11.4** (J2 Ø8 not needed) |
| LED | Ø6.5 | user fits it (gasket) | Ø6.5 |
| USB slot (cable overmould to the DevKit socket) | 12 × 8 | good: ~1 mm around a typical overmould | **12 × 8** |
| 3.0/3.2/3.4 | as drawn | not reported | — |

Plate **v2** (`cad/test_plate.py` now builds it, 120 × 44 × 2.5 mm, one row R / F / DB9 / J / USB) checks
these values; v1 is in git history (6fc8991), its picture `cad/test_plate_guide.png` shows v1.
Engraved 0.6 mm text prints messy on a top surface, so the lid logo (below) is engraved on the face printed against the bed.
**Plate v2 printed 2026-11-12: everything fits** (rocker, fuse holder, DB9 + standoffs, barrel jack, USB).
The "Use in the case" column above is final for these parts.
- **DB9 screws are short (user, 2026-11-12):** thin the wall locally to ~0.75–1.0 mm (1.5–2 mm less than the
  2.5 mm wall) in a pocket ~34 × 15 mm (flange 32 × 13 + 1 mm) on the flange side, so the screws reach and
  the flange sits keyed in the pocket. The rest of the wall stays 2.5 mm.

## Main board (draft 2026-11-12)
Perfboard 26 × 31 holes, mounting holes 83.7 × 64.6 mm centre to centre (4 corners, holes ~Ø3.1): `mainboard.svg/.png`, generated by `tools/mkmainboard.py` (stdlib; edit the
tables there and re-run). ESP32 in 2× 19-pin female headers (rows 10 holes apart), J1/J2 6-pin sockets for the
carriers (standing), J3 6-pin socket for the line board (stripboard 25 × 12, standing along the right edge,
parts facing out), J4 power (+12 V, GND, +5 V buck, GND), J5 LED (R1 330 Ω on board), J6 RING, C1 bulk cap on 3V3.
J3 pinout: 1 DAC GPIO25, 2 GND, 3 +12 V (loop feed), 4 +5 V (relay coil), 5 GPIO27 (relay, spare), 6 GND. The line
board is free to change until the modems are tested; the main board does not depend on it.
Connectors to panel parts: **JST (2.5/2.54 mm, keyed, latching; user has 2–8 pin male and female)** for J4 power (4-pin,
cannot be swapped: 12 V on the 5 V pin would kill the ESP32), J5 LED, J6 RING, and the line pairs from the line
board to each RJ12 board (2-pin). The carriers and the line board plug straight into female sockets.

**Build status (2026-11-12):** soldered: ESP32 headers, J1/J2, C1 470 µF on 3V3, wires 1–2 and 6–17 (3V3/GND and all
carrier data lines). Tested with a second ESP32 (D0WD rev v3) in the headers, USB power only:
clean boot, no brownout with BT up. J1: Courier answers `OK`; loopback plug → DCD follows DTR, `AT` echo in 24 ms.
J2: loopback plug → DCD follows DTR, echo in 20 ms. Carrier #1 (dialer) in J1, #2 in J2. Still to solder: J3 line
board (wires 18–23), J4 power (3–5, 20–21; check 5.0 V at L2–B20 with the ESP32 out first), J6 RING (24–26),
J5 + R1 LED (27–28).
All wires soldered later on 2026-11-12. Tested on USB: RING (GPIO4) → `button held 1550 ms`, call (clip + tone
fallback without modem), LED (GPIO2) flashes twice at boot and blinks during a call. Gotchas on the way: a badly
crimped JST and a wire traced to the wrong ESP pin gave `button held 0 ms` (a short dip, never held low).
Still to test: power from J4 (12 V harness, buck) without USB.

## Case model (v1, 2026-11-12)
`cad/case.py` (FreeCAD, headless: `freecadcmd cad/case.py`) builds the base and lid, stand-in blocks for the
parts, `cad/case_base.stl` + `cad/case_lid.stl` (lid flipped for printing, top face down) and the pictures
`notes/case3d_outside.png` / `case3d_inside.png`. Coordinates: x left to right seen from the front, y front to back.
- **170 × 110 × 72 mm** outside (height kept, user), 2.5 mm walls; lid 2.5 mm with a 4 mm locating lip, 4× M2
  into inserts in corner posts (Ø8, 0.5 mm into both walls).
- **Front (faces the Couriers, user's layout):** DB9 dialer (x 45) and answerer (x 82), high (z 50), pockets
  thinning the wall to 0.9 mm; line jacks low (x 113.15 / 130.85, z 19.8, 14.5 × 11.7); RING Ø12 (x 150, z 30;
  scrap pushbutton, file if snug) and LED Ø6.5 above it (z 52).
- **Back:** USB slot at the ESP32's socket, power switch (kept on the back, user), 12 V barrel jack (cradle), fuse.
- **Inside:** main board on 4 bosses (ESP32 USB end at the back wall, antenna ~40 mm from the DB9 shells),
  LM2596 on 2 solid pads (drill in place), line jack board hot-glued on one 34 × 6 × 10 mm ledge (user).
  Ribbons (~25 cm) fold above/beside the carriers; tallest part ~10 mm under the lid.
- **Lid logo (2026-11-13):** the user's XECAZ logo (`cad/logo_xecaz.jpg`) engraved 0.6 mm into the lid top,
  113 mm wide (2/3 of the lid), centred, reading from the front edge. `python3 -I tools/mklogo.py 113 140 1 0.35`
  (width mm, threshold, dilate cells, cover) → `cad/logo_xecaz.pbm` (0.2 mm cells) + `notes/logo_lid_preview.png`;
  `case.py` cuts it if the PBM exists (rebuild ~1.5 min). Lines ~0.6–0.9 mm wide for a 0.4 mm nozzle.
- **Printed 2026-11-13 (user):** logo "looks perfect", the case "fits like a glove".


- **Heat-set inserts on hand: M2 × 3 × 3.5** (length 3, outer Ø3.5; next size the user has is M4, too big).
- Main board (holes ~Ø3.1) and LM2596 (~Ø3): **M2 screw + M2 washer** (the head only just covers Ø3.1) into an
  insert in a printed boss.
- Boss: insert hole modelled **Ø3.5** (prints ~0.4 small → ~Ø3.1, a bit under the insert's 3.5 so it grips;
  check on the first print), **4–4.5 mm deep** (insert + room for melt), boss **Ø ≥ 7 mm**, 6–8 mm tall under
  the main board so the solder side clears the floor. LM2596: the Ø12 pads from before, same insert hole.
- **Boss test piece (`cad/test_boss.py`, printed 2026-11-12):** Ø3.3 / 3.5 / 3.7 holes → **Ø3.5 best** (kept).
  Lid screw hole Ø2.4 and counterbore Ø4.5 were 1 mm too small → **Ø3.4 through, Ø5.5 × 1.2 counterbore**.

## Cables
- Box DB9 male = like a PC serial port (DTE). Use standard DB9F → DB25M **modem** cables (straight, not null-modem).
- If you use MAX3232 modules that already have a DB9 soldered on, check their pinout. Many are wired as DCE, which would need a
  null-modem. Wiring the MAX3232 to panel DB9 males yourself, per `wiring.md`, avoids that.

## Inside (see top view)
- Perfboard (~67 × 45 mm): 2× MAX3232, SM-LP-5001, 470 Ω, caps, headers to the panel parts.
- Buck module next to the fuse/barrel corner, DevKit front right with USB at the front wall.
- Stand-offs or hot glue; strain relief is not needed (all cables plug into panel connectors).

## Open
- Barrel jack, power switch and RJ11 jacks are salvaged PCB-mount parts (old DSL modem): measure them and
  print holders/brackets; the cutout sizes above change to fit them.
- Pick the actual parts, then confirm every cutout from their datasheets.
