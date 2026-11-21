#pragma once
/* BLE trigger: one GATT service on Bluedroid. Phone calls also arrive here: the Android app writes
 * 0x01 when the phone rings (notes/ble.md).
 *
 * Contract for the app (also in notes/ble.md):
 *   Service  2139d581-b04a-4808-8e1f-f08bb13d8de6
 *   Trigger  2139d582-...  write (encrypted link). 0x01 = ring, 0x02 = identify (blink the LED
 *                          3 times, no call, no rate limit).
 *   Status   2139d583-...  read + notify (encrypted). 1 byte, ble_status_t.
 *   Advertised name "doorbell"; the service UUID is in the advertising data.
 *
 * Queued ("prepare") writes are refused; trigger writes of one link closer together than 250 ms are dropped; a link that is
 * not encrypted 8 s after connecting is disconnected (not while pairing).
 *
 * Only bonded devices can use it: both characteristics need an encrypted link, and new
 * pairings (Just Works, LE Secure Connections) are accepted only while the pairing
 * window is open (long-press RING or BOOT). The window closes after the first new pairing. */
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

enum { BLE_CMD_RING = 0x01, BLE_CMD_IDENTIFY = 0x02, BLE_CMD_RING_NET = 0x03,
       BLE_CMD_TONE_BASE = 0x10, BLE_CMD_TONE_MAX = 0x2f,     /* 0x10 + n: ringtone n (RINGTONES in config.h) */
       BLE_CMD_SAY = 0x40 };   /* followed by 1..SAY_MAX_WORDS word numbers (tools/vocab.txt): say that sentence */
/* 0x03: internet call (WhatsApp etc.) */

typedef enum {
    BLE_STATUS_IDLE = 0,
    BLE_STATUS_CALLING = 1,
    BLE_STATUS_COOLDOWN = 2,   /* a queued ring is waiting for its turn (triggers are still accepted) */
    BLE_STATUS_PAIRING = 3,    /* pairing window open */
} ble_status_t;

esp_err_t ble_init(void);
void ble_set_status(ble_status_t s);
void ble_pairing_open(int seconds);
void ble_pairing_close(void);
bool ble_pairing_is_open(void);
void ble_forget_all(void);
/* True when the Bluetooth stack has stopped answering its periodic health check: the caller should restart. */
bool ble_is_stuck(void);
