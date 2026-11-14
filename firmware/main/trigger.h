#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"

typedef enum {
    TRIG_RING_BUTTON = 0,   /* front panel, GPIO4 */
    TRIG_BOOT_BUTTON,       /* onboard BOOT, GPIO0 */
    TRIG_BLE,               /* GATT write 0x01 from the app */
    TRIG_BLE_IDENTIFY,      /* GATT write 0x02: blink the LED, no call */
    TRIG_BLE_NET,           /* GATT write 0x03 from the app: internet call (WhatsApp etc.) */
    TRIG_BLE_TONE,          /* GATT write 0x10 + n (or console :ring n): ringtone n from RINGTONES (config.h) */
    TRIG_COUNT
} trigger_src_t;

void trigger_init(void);
/* Post a trigger from task context (BLE writes). */
void trigger_post(trigger_src_t src);
/* Post ringtone n (task context). The id of the latest post is kept; triggers during a call are dropped anyway. */
void trigger_post_tone(uint8_t id);
uint8_t trigger_tone_id(void);
/* Block until a trigger arrives; false on timeout. */
bool trigger_wait(trigger_src_t *src, TickType_t timeout);
/* Drop triggers that queued up during a call. */
void trigger_clear(void);
const char *trigger_name(trigger_src_t src);
