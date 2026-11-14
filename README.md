# modem.doorbell

A doorbell whose chime is a 1990s dial-up handshake.

An ESP32 drives two US Robotics Courier modems that are wired back to back on a closed, private line. On a
trigger, the dialing modem goes off-hook (click), the ESP32 plays a European 425 Hz dial tone onto the
line, the modem dials a DTMF digit, the other modem answers, and the two handshake. That screech, from
the dialing modem's speaker, is the doorbell.

**Never connected to a real phone line.** The two modems only ever talk to each other.

## Triggers
- **RING button** on the box (or the ESP32's BOOT button on the bench).
- **Android app** over Bluetooth LE: a RING button, plus "ring when my phone rings". That covers regular
  calls and internet calls (WhatsApp, Signal, ...), and works with the app closed.
- Rate limit: one call per 30 s.

Only bonded phones can trigger it. New phones can pair only during a 60 s pairing window, opened by holding
the button for 3 s.

## Hardware
- Original ESP32 (WROOM-32) DevKit: BLE plus the DAC for the dial tone.
- 2× MAX3232 for RS232 to the modems (TX/RX plus DTR/DCD).
- Bourns SM-LP-5001 600:600 line transformer to couple the dial tone onto the line.
- 12 V supply, 12→5 V buck, fuse, 3D-printed case.

Wiring, pin map and call sequence: [`notes/wiring.md`](notes/wiring.md). Case: [`notes/case.md`](notes/case.md).
BLE protocol: [`notes/ble.md`](notes/ble.md).

## Layout
| Path | What |
|---|---|
| `firmware/` | ESP-IDF 5.5 project in C: call sequence, audio (dial tone and sound clips), BLE trigger. Pins and timings in `main/config.h`. |
| `app/` | Android app in plain Java, built with the SDK build-tools only (no Gradle, no dependencies). |
| `notes/` | Design docs and diagrams. |
| `tools/` | Small stdlib-only Python helpers: serial log capture, ESP32 chip ID, sound-bank builder. |

## Build
Firmware (ESP-IDF v5.5):
```sh
. $IDF_PATH/export.sh
cd firmware && idf.py build && idf.py -p /dev/ttyUSB0 flash monitor
```

Android app (Android SDK with build-tools 36.1 and platform 36, JDK 17+):
```sh
app/build.sh
adb install -r app/build/doorbell.apk
```

## Status
Firmware and app work without the modems: buttons, BLE pairing, ringing from the app and on incoming
calls, the dial tone on the DAC. The modem side (RS232 wiring, the AT call sequence, the tone on the
line) is waiting for parts.

## Hardware notes
- An ESP32 DevKit powered from USB can brown out when Bluetooth starts. Put 100–470 µF between 3V3 and GND.
- Some DevKits have no user LED on GPIO2, and some label the flash pins "D0–D3". Don't connect anything there.
