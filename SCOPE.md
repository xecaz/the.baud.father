# SCOPE: modem.doorbell

**Confirmed: no**   (set to `yes` once the boundaries below are right)

## Purpose
- Alarm/doorbell kit: an ESP32 receives a trigger (BLE button, Android app, later an incoming-call
  indication: the Android app sends the BLE trigger when the phone rings), injects a fake European dial tone (425 Hz) onto a private phone line,
  and makes two owned US Robotics Couriers (two V.Everything: one dialer, one answerer) handshake.
  The handshake through the Courier speaker is the alarm sound.

## Boundaries
- Runs locally only: yes. Owned hardware, closed back-to-back line between the two modems.
- Never connected to a real PSTN/operator line (no ring/loop voltage from outside, no real dialing).
- Bluetooth: only the user's own phone and BLE button pair with the ESP32.
- Touches third-party systems: no.
- Dependencies: zero-dependency by default. ESP-IDF toolchain via PlatformIO on the laptop; any
  extra component/library needs explicit approval (see the conventions in the project notes).
