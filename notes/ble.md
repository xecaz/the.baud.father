# BLE trigger (GATT contract)

Source of truth for the firmware (`firmware/main/ble.c`, `ble.h`) and the app (`app/`). Change both together.

## Advertising
- Name **`doorbell`** (scan response), connectable, ~160–200 ms interval.
- The service UUID is in the advertising data (complete list of 128-bit UUIDs), so apps scan with a
  service-UUID filter.
- Address: the ESP32's public BT address (fixed per board, shown in the boot log as "Bluetooth MAC").

## Service `2139d581-b04a-4808-8e1f-f08bb13d8de6`

| Characteristic | UUID | Properties | Value |
|---|---|---|---|
| Trigger | `2139d582-b04a-4808-8e1f-f08bb13d8de6` | write (encrypted link) | `0x01` ring, `0x02` identify (blink the LED 3×, no call, no rate limit), `0x03` ring for an internet call (WhatsApp etc.: the box plays the `v90` clip as the handshake, dialer only; a normal call if the clip is missing). `0x10 + n` (up to `0x2f`): ringtone n from the box's table (`RINGTONES` in config.h; 2026-11-14, run from the console with `:ring n`, not yet from the app): 0 call, 1 56k clip, 2 "whatsapp" spoken, 3 "signal" spoken, 4 failed negotiation + redial, 5 "email" spoken, 6 demo, 7 "food update" spoken; since the same day `0x01` rings ringtone 4 and `0x03` ringtone 0; an unknown n rings like `0x01`. `0x40` followed by 1 to 16 word numbers: say that sentence (see "Say"). Other values are ignored. |
| Status | `2139d583-b04a-4808-8e1f-f08bb13d8de6` | read + notify (encrypted) | 1 byte: `0` idle, `1` calling, `2` a queued ring is waiting (triggers are still accepted), `3` pairing window open |

Both characteristics and the status CCCD need an **encrypted, bonded link**; the stack rejects
unencrypted access.

## Pairing
- LE Secure Connections, **Just Works** (the box has no display or keypad), bonding. Bonds are kept in NVS
  and survive reflashing the app (not an NVS erase).
- New pairings are accepted **only while the pairing window is open**: hold RING or BOOT for **3–9 s**
  (window lasts 60 s; the LED on GPIO2 blinks fast). Outside the window pairing requests are rejected
  (`REJECTED (window closed)` in the log). Just Works has no MITM protection; the window is what keeps
  strangers out.
- Hold **10 s or more**: forget all bonds. Phones then have to remove "doorbell" from their Bluetooth
  settings and pair again.
- A call (any trigger) closes the pairing window.

## Phone calls (app side)
- **Regular calls:** `CallReceiver` gets the system `PHONE_STATE` broadcast (exempt from Android's
  implicit-broadcast limits, so it is delivered with the app closed; a protected broadcast, so other apps
  cannot fake it: verified, `SecurityException` from the adb shell). Permission: READ_PHONE_STATE.
- **Internet calls (WhatsApp, Signal…):** they do not change the phone state. `CallNotificationListener`
  (notification access, granted by hand in Android settings) rings on notifications with category `call`
  that are incoming (CallStyle `CALL_TYPE_INCOMING`, or a full-screen intent without CallStyle). Reads no
  titles, text or caller names.
- Internet calls send `0x03`; the default dialer's own call notification (a regular call) sends `0x01` (app 0.4, 2026-11-14).
- One ring per call (per notification key), and the app skips a second ring within 20 s (a regular call
  fires both detectors).
- Background ring: connect to the bonded box by address (no scan), write `0x01`, disconnect. Measured
  2026-11-07: WhatsApp notification → ring written in 122 ms.
- Not after "Force stop" in Android settings (Android blocks all background events until the app is opened).

## Say (vocabulary; 2026-11-21, tested from the console and from the laptop)
One write of `0x40, w1, w2, …` (1 to 16 word numbers, `SAY_MAX_WORDS`) makes the box say those words in that order.
- The words are in `tools/vocab.txt`; a word's number is its position there (0 = a short pause). The list is append
  only, because senders store numbers.
- The firmware does not know the words: word n is the bank clip named `wNNN.<word>` (`tools/mkspeech.py --vocab`,
  then `tools/mksounds.py`). New words need a new sound bank, not a new firmware. A number with no clip is left out.
- A sentence queues like a message (see "Queue"): several are said in one off-hook, and one that arrives during a
  call is said after the hang-up. The same sentence is not queued twice, and not repeated within 8 s.
- The whole write is 2 to 17 bytes, so it fits a plain 20-byte write (queued writes stay refused).
- Senders: `python3 -I tools/say.py 3 new messages` (laptop), console `:say 4 72 49`, the app's "Say…" button
  (app 0.8; `app/build.sh` packs `tools/vocab.txt` into the app, so rebuild the app after adding words).

## Queue (replaces the rate limit; 2026-11-18, tested from the console with `:ring`)
Triggers that arrive while the box is busy wait in a short list (6 entries, `PEND_MAX`) instead of being dropped.
- **Messages** (spoken ringtones) are said one after the other in one off-hook, 1 s apart. One that arrives during a
  call is said right after the hang-up, before the modem reset.
- **Calls** (everything else) go ahead of waiting messages. At most one call waits; the next call starts no sooner
  than 8 s after the previous one ended (`TRIGGER_CALL_GAP_MS`); Status reads `2` while it waits.
- The same spoken ringtone is not repeated within 8 s, and a ring that waited more than 45 s is dropped.
- Button presses during a ring are ignored, as before.
- The modem reset after a call resets both modems side by side (about 2.2 s instead of 4.5 s).
- App 0.7: message sounds are sent at least 1 s apart (was: none within 10 s of any ring).
- Tested 2026-11-18: two messages in one off-hook; messages during a call said after the hang-up; a queued second
  call connected; the failed-negotiation ringtone with a message in between; phone and laptop sending at the same moment.

## Tested 2026-11-07
- Phone: Android 16, app `lab.modemdoorbell` 0.1. Pairing inside the window: accepted, bonded,
  ring/identify/status notifications work, rate limit works. Pairing outside the window: rejected.
  Reconnect after reflash: no re-pairing needed.

## Connections (2026-11-14)
Up to 3 centrals at once (`BLE_MAX_LINKS`, ble.c): the box advertises again after each connect while a slot is free, and
status notifications go to every link that enabled them. One sound at a time: triggers during a ring are queued (see "Queue").

## Hardening (2026-11-15 shakedown)
Tested with a raw ATT client from a bonded laptop, on unencrypted and encrypted links.
- **Queued ("prepare") writes are refused** on the trigger and the status CCC (`request not supported`). Both are
  answered by `ble.c` (`ESP_GATT_RSP_BY_APP`). Reason: with `ESP_GATT_AUTO_RSP`, ESP-IDF 5.5.1 Bluedroid stores each
  prepare write in a 254-entry queue and enqueues with an infinite timeout inside its own task
  (`gatt_attr_process_prepare_write`, `stack/gatt/gatt_sr.c`), so prepare write 255 without an execute blocks the stack
  for ever: no advertising, no answers, no reboot. Reproduced on the box; needed an encrypted link here.
- **Unencrypted links are dropped after 8 s** (not during the pairing window + 20 s), so idle strangers cannot hold
  the 3 link slots.
- **Pairing:** LE Secure Connections only, 16-byte keys only, one new device per pairing window.
- **Trigger writes** of one link closer together than 250 ms are dropped (per link since the queue, so two devices writing at once both count). Trigger length must be 1 to 17 bytes (was 4 before "Say"), CCC exactly 2.
- **Health check:** every 30 s a request goes through the whole stack; two unanswered ones restart the box (between
  calls). The task watchdog now reboots too, and stack/heap checks are on (`sdkconfig.defaults`).
  The restart path has not been exercised by a real hang since the fix (nothing hangs it any more).
- Not done: flash encryption / secure boot (bond keys are readable with physical access), private address.
- Not tested: pairing refusal outside the window and legacy-pairing refusal (need a second, unbonded device).
