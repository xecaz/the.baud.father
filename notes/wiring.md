# Wiring (design B + dial tone injection, Europe)

Status: draft 2026-11-05, nothing built or measured yet. "start" = starting value, tune on the bench.

Picture: `wiring.svg` (source, edit this) and `wiring.png` (rendered with `rsvg-convert -b white -o wiring.png wiring.svg`).
Keep the picture and this file in sync.

## Block diagram

```
 Android app over BLE (button, incoming calls)
                 │  Bluetooth
        ┌────────▼─────────┐
        │   ESP32 (WROOM)  │
        │                  │ UART2 + DTR/DCD   ┌──────────┐  DB9→DB25   ┌────────────────────┐
        │                  ├───────────────────► MAX3232 #1├────────────► Courier V.Everything │ dialer
        │                  │                   └──────────┘             └─────────┬──────────┘
        │                  │ UART1 + DTR/DCD   ┌──────────┐  DB9→DB25   ┌─────────┴──────────┐
        │                  ├───────────────────► MAX3232 #2├────────────► Courier Dual Std    │ answerer
        │                  │                   └──────────┘             └─────────┬──────────┘
        │          GPIO25  │  DAC 425 Hz       ┌──────────────┐                   │
        │          (DAC1)  ├───────────────────► SM-LP-5001   ├──── line pair ────┘ (both LINE jacks
        └──────────────────┘                   │  600:600     │                      on one pair)
                                               └──────────────┘
```

## ESP32 pin map

| Function | GPIO | Notes |
|---|---|---|
| Dialer TX (UART2) | 17 | → MAX3232 #1 T1IN |
| Dialer RX (UART2) | 16 | ← MAX3232 #1 R1OUT |
| Dialer DTR | 18 | → MAX3232 #1 T2IN. **Inverted:** GPIO low = DTR on, high = DTR off (hang up) |
| Dialer DCD | 19 | ← MAX3232 #1 R2OUT. **Inverted:** low = carrier |
| Answerer TX (UART1, remapped) | 32 | → MAX3232 #2 T1IN |
| Answerer RX (UART1, remapped) | 33 | ← MAX3232 #2 R1OUT |
| Answerer DTR | 21 | → MAX3232 #2 T2IN (inverted, as above) |
| Answerer DCD | 22 | ← MAX3232 #2 R2OUT (inverted, as above) |
| Audio out (dial tone, clips) | 25 | DAC1 via DMA (8 kHz), powered down (hi-Z) when not playing |
| RING panel button | 4 | Momentary to GND, internal pull-up, active low. Front-panel bench trigger |
| Local test trigger | 0 | Onboard BOOT button only (strapping pin: no panel button here) |
| Status LED | 2 | Onboard LED; panel LED also on GPIO2 through 330 Ω–1 kΩ |

UART0 (GPIO1/3) stays on USB for flashing and logs.

Board: AZ-Delivery DevKitC-style, 38 pins, ESP32-WROOM-32, micro USB, CP2102 (`/dev/ttyUSB0`). Header labels are
plain GPIO numbers; D0–D3/CMD/CLK are the flash lines (never connect). No onboard user LED (red = power).
Chip read 2026-11-06: ESP32-D0WD rev v3, dual core, BT enabled. WROOM (no PSRAM), so GPIO16/17 are free.
All GPIOs above are on the header.

## MAX3232 (one per modem, powered from 3.3 V)

Use a module or bare chip that exposes **both** channels (T1/T2, R1/R2). Many cheap DB9 modules only
wire TX/RX; then DTR and DCD are missing (see fallback below).

```
 ESP32               MAX3232                 DB25 on Courier (modem = DCE)   via DB9 adapter
 TX  ───────────── T1IN   T1OUT ───────────  pin 2  TxD (data to modem)      DB9 pin 3
 RX  ───────────── R1OUT  R1IN  ───────────  pin 3  RxD (data from modem)    DB9 pin 2
 DTR ───────────── T2IN   T2OUT ───────────  pin 20 DTR                      DB9 pin 4
 DCD ───────────── R2OUT  R2IN  ───────────  pin 8  DCD                      DB9 pin 1
 GND ───────────── GND          ───────────  pin 7  Signal ground            DB9 pin 5
 3V3 ───────────── VCC   (+ 4x 0.1 µF charge-pump caps + 0.1 µF bypass if bare chip)
```

**Mini "RS232<->TTL" modules, HW-027** (10 arrived 2026-11-09; used in the box): caps on the back. Both
channels are broken out (mapped 2026-11-09 with a continuity meter):
- **Round through-hole pads = power** (+ and −, at each end), the same copper on both sides.
- **Square pads are one-sided:** the 4 on the **front** are **channel 2**, the 4 on the **back** are **channel 1**.

So on this board data uses channel 2 and DTR/DCD use channel 1 (the diagram above has them the other way
round; the firmware does not care). Chip seen from the top with the pin-1 dot bottom-left (bottom row 1–8,
top row 16–9, left to right); front TTL pads on the right, RS232 pads on the left.

| Side | Pad | Pin | Goes to |
|---|---|---|---|
| both | round "−" | 15 GND | DB9 5 and system GND |
| both | round "+" | 16 VCC | 3V3 |
| front, left | "->" | 8 R2IN | DB9 2 (RxD from the modem) |
| front, left | "<-" (bottom) | 7 T2OUT | DB9 3 (TxD to the modem) |
| front, right | "->" (top) | 9 R2OUT | ESP RX (GPIO16 / 33) |
| front, right | "<-" | 10 T2IN | ESP TX (GPIO17 / 32) |
| back | square | 11 T1IN | ESP DTR (GPIO18 / 21) |
| back | square | 14 T1OUT | DB9 4 (DTR) |
| back | square | 13 R1IN | DB9 1 (DCD) |
| back | square | 12 R1OUT | ESP DCD (GPIO19 / 22) |

Find each back pad with the meter from its chip leg before soldering (none of 11–14 reaches a front pad).

**Carriers (built 2026-11-10, both identical; drawing `hw027.svg/.png`).** Each HW-027 sits on a stripboard
carrier with a 6-pin header into the breadboard / main board; the RS232 side goes straight to a DB9 male on a
9-wire ribbon (IDC plug cut off, wire 1 = red stripe; alternating order, metered):

| Carrier pin | Signal | Pad | Dialer | Answerer |
|---|---|---|---|---|
| 1 | + 3V3 | round + | 3V3 | 3V3 |
| 2 | − GND | round − (+ ribbon 9 = DB9 5) | GND | GND |
| 3 | TX | 10 T2IN | GPIO17 | GPIO32 |
| 4 | RX | 9 R2OUT | GPIO16 | GPIO33 |
| 5 | DTR | 11 T1IN | GPIO18 | GPIO21 |
| 6 | DCD | 12 R1OUT | GPIO19 | GPIO22 |

| Ribbon wire | DB9 | Pad |
|---|---|---|
| 1 (red) | 1 DCD | 13 R1IN |
| 3 | 2 RxD | 8 R2IN |
| 5 | 3 TxD | 7 T2OUT |
| 7 | 4 DTR | 14 T1OUT |
| 9 | 5 GND | − |
| 2, 4, 6, 8 | 6–9 | cut, not connected |

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | C1+ | 16 | VCC (3V3) |
| 2 | V+ | 15 | GND |
| 3 | C1− | 14 | T1OUT (back pad, DTR) |
| 4 | C2+ | 13 | R1IN (back pad, DCD) |
| 5 | C2− | 12 | R1OUT (back pad, DCD to ESP) |
| 6 | V− | 11 | T1IN (back pad, DTR from ESP) |
| 7 | T2OUT (front pad, TxD) | 10 | T2IN (front pad, ESP TX) |
| 8 | R2IN (front pad, RxD) | 9 | R2OUT (front pad, ESP RX) |

Test each on 3.3 V: pin 2 ≈ +5.5 V, pin 6 ≈ −5.5 V, T2OUT and T1OUT ≈ −5.5 V idle (input high or floating
high); loopback 7→8 (data) and 14→13 (DTR/DCD).
**Tested 2026-11-11 on their own pins:** carrier #1 on the dialer (GPIO17/16/18/19), carrier #2 on the
answerer (GPIO32/33/21/22), with DB9 2–3 and 1–4 looped (a female DB9 plug with both shorts is the bench
loopback). Boot log: `<name> -> AT` echo, then `DCD follows DTR (DB9 1-4 loopback OK)`.
The HW-044 DB9 modules (8, bench use) are not mapped.

RTS/CTS are not wired. The init string turns off hardware flow control (`&H0&R1`), verify with `ATI4`.

**Fallback without DTR/DCD:** set DIP 1 to DTR override, hang up with `+++` (1 s guard time each
side) then `ATH`, and detect the connection by parsing `CONNECT` on RX.

## Line side

### Modem to modem
Both Couriers' **LINE** jacks on the same pair (RJ11 centre pins, 3 and 4 of a 6P4C plug), via an RJ11
splitter or a small terminal block. Polarity does not matter.

### Loop voltage (only if they won't handshake without it)
```
 Dialer tip  ──────────────────────────────────  Answerer tip
 Dialer ring ──[ 470 Ω start ]──[ + 12 V rail − ]──  Answerer ring
```
12 V and 470 Ω give roughly 10–15 mA with both modems off-hook. If they drop the line, go down toward 220 Ω.

**Loop feed is required, 150 Ω (tested 2026-11-14).** The answerer (V.Everything 56K, "CTR21 External") checks the line:
- No feed (JP1 B–C): `ATA` → `NO DIAL TONE` after 4.6 s, no answer tone (also alone, also with `X3`: it is a line-voltage
  check, not dial-tone detection). The dialer has no such check and dials into a dead line.
- Feed with 470 Ω (JP1 A–B + C–D): it picks up and sends answer tone, then `NO CARRIER` 6.68 s after `ATA` (same with the
  dialer only parked off-hook with `ATH1`). Measured 4.27 V across R2 = **9 mA**: too little. The two off-hook modems
  drop about 7.6 V together.
- **470 Ω ∥ 220 Ω = 150 Ω: `CONNECT 9600/ARQ/V34/LAPM`** 11.0 s after `ATA` (first handshake; log
  `log/handshake-150R-20261114-160742.log`). Current with 150 Ω not measured yet (expected ~20 mA+).
- A JP1 cap that slipped gave the no-feed `NO DIAL TONE` again: fix the caps (or solder the links) before closing the box.
- The feed is a series loop: current flows only while **both** modems are off-hook (0 V across R2 otherwise).
- Open: `9600` in the CONNECT line may be the link rate or the fixed DTE rate (`&B1`, 9600); `ATI6` right after a call,
  before the firmware's `ATZ`, would tell.

## Power

```
 12 V DC adapter ─► barrel jack ─► fuse ─► 1N5819 ─► power switch ─┬─► +12 V rail ─► loop feed (+, via 470 Ω)
 (5.5/2.1, centre +)             T500 mA                           │
                                                                   └─► buck 12→5 V ─► DevKit 5V pin
                                                                                        └─► DevKit 3V3 ─► MAX3232 #1, #2
 GND: adapter −, buck −, ESP32 GND, loop feed − all common.
```
- **Bulk cap on 3V3 (required):** electrolytic 100–470 µF, 6.3 V+, between the DevKit's 3V3 and GND pins
  (minus to GND), close to the module. Without it the board browned out at every boot from 2026-11-07
  11:11: the RF calibration burst when Bluetooth starts sagged the rail so far that the ESP32 and the
  CP2102 both reset (USB re-enumerating ~3×/s, log ending at `phy_init: ... full calibration`). The
  same firmware had run fine earlier on the same board, so the board's USB/regulator path is marginal.
  Fitted 2026-11-07, fixed it. Firmware without Bluetooth never showed it.
- ESP32 runs at 3.3 V. The DevKit's own regulator makes it from 5 V, so feed 5 V, never 12 V, into the DevKit **5V** pin (check the silkscreen: some boards call it VIN).
- Buck: any small 12→5 V module (MP1584 or LM2596 type), 1 A+ is plenty (ESP32 with BT peaks ~250–500 mA).
  **Set the output to 5.0 V with a multimeter before connecting the ESP32**; they often ship set much higher.
- Fuse: 5×20 mm slow-blow, T500 mA (total draw at 12 V is about 0.3 A at most).
- Reverse-polarity protection: a Schottky (1N5819, on hand) in series after the fuse (drops ~0.3 V).
- Sharing the 12 V between ESP32 and loop feed is fine: the Couriers' line side is isolated by their own
  transformers and the ESP32 only touches the line via the SM-LP-5001. For a fully floating line, use a
  separate small 12 V adapter for the loop feed.
- **Bench-tested 2026-11-12** (test rig, not the case wiring): adapter 12.3 V unloaded, centre +, 2.5 A →
  fuse (1 A stand-in) → 1N5819 → rocker → LM2596 module set to 5.0 V → DevKit 5V pin. Loaded: 5V pin 4.95 V,
  3V3 3.2 V. BOOT played the dingdong through the transformer/amp with USB unplugged.
- **USB and the buck can be connected at the same time:** the board has a diode after USB (5V pin read
  4.47 V on USB alone, i.e. ~0.5 V Schottky drop), so the buck's 5.0 V does not feed back into the laptop.
  Logs and the AT console keep working while the box runs on its own power.
- The Couriers keep their own power adapters. Firmware waits ~3 s after power-up before sending AT
  commands, in case everything is switched on at once.

### Dial tone injection (SM-LP-5001)
**Line board on the line, 2026-11-14:** tone traced stage by stage with a scope (DAC pin 1.68 V avg, F, B10, C9, C3–E3 all
carry the sine; G–C2 = 1.63 Vpp unloaded) and **heard from the dialer's speaker** (`:d`, `ATM2H1`, `:tone`), clips too
(`:play tada`). The first failure (click + DTMF but no tone) was most likely an RJ plug not fully seated at the box end;
wiggle test afterwards clean. Scope lesson: a loose ground clip shows 50 Hz hum and ~0 V avg everywhere (the multimeter
readings at F/B10 were misleading too). Scope read 566 Hz for the 425 Hz tone: by ear it sounds right, not verified.

**Line board layout (2026-11-13):** `notes/lineboard.png`, generated and netlist-checked by
`python3 -I tools/mklineboard.py` (then `rsvg-convert -b white -o notes/lineboard.png notes/lineboard.svg`).
7 strips × 12 holes off the last stripboard; cuts A6 B6 C6 E6; header pins only at J3.1/.2/.3/.6 (GPIO27 and +5 V
pins pulled); line pairs soldered to the board, JST at the jack-board end. Loop feed via JP1: no feed = B–C,
feed = A–B + C–D (12 V straight to the dialer's leg, 470 Ω in the answerer's leg to GND).

```
 GPIO25 ──[+ 10 µF −]──[ 680 Ω       ]──┐ 1        6 ┌──[ 1 µF, 50 V+     ]── line tip
                                        │ winding A  │ winding B
                                        └──(  SM  )──┘
 GND ───────────────────────────────────┘ 3 LP-5001 4└──────────────────────── line ring
```
Pinout from the [Bourns datasheet](https://www.bourns.com/docs/Product-Datasheets/SM-LP-5001.pdf) (rev. 04/11): **winding A = pins 1–3, winding
B = pins 6–4, pins 2 and 5 not connected**, 115 Ω ±15 % DC each. Symmetrical (no real primary/secondary);
dots on 1 and 6 (phase, does not matter here). Seen from the top: 1-2-3 down the left side, 6-5-4 down the
right, pin 1 top left. Legs 2.54 mm pitch, rows ~15 mm apart (6 holes = 15.24 mm). 600 Ω 1:1, ±0.25 dB
200 Hz–4 kHz, insertion loss ≤ 2 dB, max 10 dBm (~2.4 V rms on 600 Ω), 2000 V rms isolation. No DC through
either winding (10 µF and 1 µF block it).
- **Breadboard mount:** straight header pins soldered to the gull-wing feet; it straddles the centre channel
  like a DIP, pins 1–3 in row c, 6–4 in row g (exactly 6 holes). On stripboard, cut every strip under the
  body, or the two windings short together. Meter after soldering: 1–3 and 6–4 ≈ 115 Ω, all else open. Measured 2026-11-11: ~100 Ω each (in tolerance, 98–132 Ω), all other pairs open.
- 10 µF electrolytic: + toward the ESP32 (DAC idles around 1.65 V).
- Measured 2026-11-07, bare GPIO25 to GND, multimeter on AC: tone **~0.4 V AC** with `DAC_COSINE_ATTEN_DB_6`
  (half amplitude, ~1.1 V peak-to-peak; a cheap meter may read low at 425 Hz). Idle, the floating pin reads
  **~0.7 V AC of mains hum**: that is the meter's 10 MΩ on a hi-Z pin, not the DAC. The reading drops to
  ~0.4 V while the DAC drives the pin and returns after, which also confirms the DAC releases the pin. In the
  circuit the 680 Ω + transformer primary tie the pin to GND, so no hum there.
- 1 µF blocks the loop DC from the winding. Film is best; an X7R ceramic rated 50 V+ is fine (the line only
  sees the 12 V loop feed, no ring voltage).
- After the tone, the DAC is **disabled** (pin hi-Z), so the transformer barely loads the line during
  the handshake. If the handshake gets flaky, add a small relay or PhotoMOS to cut the secondary.
- If the tone is too quiet: lower the 680 Ω (510 Ω), or add an op-amp buffer.
- **Bench test 2026-11-11 (tone heard through the amp):** GPIO25 → 10 µF → 680 Ω → pin 1, pin 3 → ESP32 GND;
  680 Ω across pins 6–4 as the 600 Ω line stand-in; pin 6 → 0.15 µF film (305 V AC X2) → amp tip, pin 4 → amp
  sleeve (nothing on that side to the ESP32 GND). `BENCH_TONE 1` in config.h plays the tone nonstop from boot.
  GPIO25 read 0.25 V AC loaded (0.4 V unloaded). A floating secondary (amp ground not on pin 4) read 0.7 V AC
  of hum and gave no sound: the amp's two wires must land on different ends of winding B.

## AT console (USB, firmware `console.c`)
Talk to either Courier from the laptop through the box, no USB-RS232 adapter needed (`AT_CONSOLE 1` in
config.h; starts after the boot probe).
- Interactive: `python3 -I tools/atcon.py /dev/ttyUSB0 [--log notes/at-dialer.txt]` (stdlib; does not reset
  the board). `idf.py monitor` also works, but shows no local echo.
- Scripted: `python3 -I tools/atcon.py /dev/ttyUSB0 --cmd ":d" --cmd "ATI4" --cmd ":off" [--wait 2] [--reset]`.
- `:d` / `:a` select the dialer / answerer and raise its DTR (DTR-normal Couriers ignore AT with DTR off);
  `:off` releases it. While a modem is selected, button/BLE calls are skipped (logged); a call in progress
  blocks `:d`/`:a`. `:dtr 0|1`, `:dcd`, `:esc` (`+++` with guard times), `:help`. Any other line (an empty
  one too, for "press a key" pauses) goes to the modem with CR; replies print raw.
- Tested 2026-11-11 with the loopback plug on carrier #1: `ATI4` echoed, DCD followed `:dtr`.

## Courier settings (both on RS232 in design B)

| DIP function | Dialer (V.Everything) | Answerer (V.Everything 56K, R20.0013.00) |
|---|---|---|
| 1 DTR | Normal | Normal |
| 3 Result codes | Enabled | Enabled |
| 2 Verbal codes | Verbal | Verbal |
| 5 Auto-answer | **Off** (no ring anyway) | **Off** (ESP32 sends `ATA`) |
| 8 AT commands | Enabled (smart) | Enabled (smart) |
| 10 Power-on defaults | Load NVRAM | Load NVRAM |

Switch direction (up/down) is not confirmed: read the chart on the bottom of each Courier.

### Dialer NVRAM setup (Courier V.Everything, written 2026-11-12 from the laptop)
```
AT&F1E1V1Q0X3&C1&D2&B1&H0&R1&A3&M4&K1S0=0S7=60S11=70&W
```
As found (`ATI4`, `notes/at-courier1.txt`): `&H1 &R2 X7 S0=1 S11=70 DIAL=PULSE`. **`&R2` made it silent on the box**:
it only sends while RTS is on, and RTS is not wired (cable, carrier, levels, DTR all checked fine; a USB-RS232
adapter, which raises RTS, got `OK` at once). The firmware now also sends `AT&H0&R1` blind before the probe and
after `ATZ`, so a modem with `&R2` stored still works. After `&W` + `ATZ`: `&H0 &R1 X3` stick; `S0` comes back as 1
(DIP 5 up = auto-answer at power-on/ATZ; **DIP 5 flipped down 2026-11-12**) and `DIAL=PULSE`
stays (the firmware dials with `DT`). DIP switches as found: 3 and 8 down (ON), the rest up; now 3, 5 and 8 down.
Power: 18 V AC adapter on this 20 V AC model, 19.8 V AC under load. At first power-on it whined at ~9.6 kHz
(drifting 9.4–9.65 kHz, the internal switching supply; measured from a phone video); gone after it had run a while.
Looked inside: no bulging caps, no heat marks. If it only whines when cold, the electrolytics are tired (recap some day).
**Blind dial with an empty LINE jack works (2026-11-12):** `ATM2X3S11=100` then `ATDT0123456789*#0123456789;` →
off-hook click, 22 DTMF digits on the speaker, `OK` (the `;` returns to command mode instead of waiting for a
carrier), `ATH0`. No line voltage or dial tone needed for the dialing part. Any byte sent while it dials aborts it
(`NO CARRIER`). `S11` = DTMF tone/gap length in ms: **70 stored and kept** (user: 60–70 as back in the BBS days, fast); 100 was only for the test.

### Answerer NVRAM setup (store once with the AT console: `:a`, then the string)
```
AT&F1E0V1Q0X4&C1&D2&B1&H0&R1&A3&M4&K1S0=0S7=60&W
```
Based on the user's BBS-era answer string `AT&F1E0V1Q0X4&C1&D2&B1&H1&R2&A3&M4&K1S0=1S7=60S11=70&W`,
changed for this box (2026-11-11):
- `&H1` → **`&H0`**, `&R2` → **`&R1`**: RTS/CTS are not wired. With `&R2` the modem only sends to the DTE
  while RTS is on, so it would never answer `OK` (exactly what the first Courier did, 2026-11-12). The firmware
  now sends `AT&H0&R1` blind before the probe and after `ATZ`, but storing `&R1` keeps it clean.
- `S0=1` → **`S0=0`**: design B answers with `ATA` (there is no ring on this line anyway).
- `S11=70` dropped: DTMF length only matters on the dialer (it sets how long the DTMF beep sounds there).
Kept: `&F1` base, `E0` (echo off; the firmware skips echo anyway, `atcon.py` shows what you type),
`V1Q0X4`, `&C1` (DCD = carrier, the firmware watches it), `&D2` (DTR drop = hang up), `&B1` fixed DTE rate,
`&A3&M4&K1` (ARQ/compression; `CONNECT 14400/ARQ/…` still matches the firmware's `CONNECT` prefix),
`S7=60`, `&W` (pairs with DIP 10 = load NVRAM). Verify with `ATI4` afterwards.
**Written 2026-11-14** (as found `X7 E1 S0=0`, `notes/at-courier2.txt`; after: `notes/at-courier2-after.txt`): `X4 &H0 &R1 S0=0 S7=60`
stick after `ATZ`; `E1` comes back (most likely DIP 4, as DIP 5 did with `S0` on the dialer; harmless, the firmware skips
echo). `ATI7`: CTR21 External, supervisor/DSP 2.1.1 (01/10/03), options HST, V32bis, Terbo, VFC, V34+, V90, V92,
DIP 3, 5, 8 down. Runs on a 12 V DC adapter (its own, not the box rail) through the handshake.

## Call sequence (firmware outline)

Idle (from boot, and again after every call): both modems **ready**: DTR on (TR lit), `AT&H0&R1` sent blind,
`ATH0`, `ATZ`, `AT&H0&R1` blind again, then the init (`AT&H0&R1M2X3` dialer, `AT&H0&R1` answerer) → `OK`.
`ATH0` + `ATZ` run here, in idle time, never at the trigger (2026-11-12: without them a second dialer-only call
was silent, and an ESP32 reset mid-call left the dialer OFF HOOK until an `ATH0`). A modem that does not answer
is marked missing; checked again after each call. Dialer-only calls also send `ATH0` before the DTR drop.

| t | Dialer | ESP32 | Answerer |
|---|---|---|---|
| 0 | `ATM1DT555` (door buttons) / `ATM1DT999` (BLE: calls): off-hook click at once, then the S6 wait (2 s) | trigger received | |
| +0.2 s | | DAC on, 425 Hz dial tone (inside the S6 wait) | |
| +1.7 s | | DAC off (hi-Z) | |
| +2.0 s | DTMF digits (S11 = 70 ms tone + 70 ms gap each) | | |
| digits + 0.2 s | waits for the answer tone | | `ATA` (answer tone, handshake) |
| CONNECT / DCD | speaker cuts at carrier (M1) | hold timer | |
| +N s or timeout 40 s | DTR off → on hook, then ready again | | same |

**Dialer-only** (answerer missing): `ATM1DT555;` (the `;` returns `OK` after the digits), hold 0.5 s, hang up.
Measured 2026-11-12: trigger → dial command 4 ms ("INSTANT"), `OK` after 2.7 s for 3 digits; ready again ~10 s
after the trigger; 3 calls in a row all dialed.

Timings are guesses; tune by ear. Rate-limit triggers (e.g. ignore new ones for 30 s after a call).

## Safety
- Never connect this line to a real phone socket.
- The ESP32 is only ever coupled to the line through the transformer and capacitors.
