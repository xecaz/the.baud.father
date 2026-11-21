#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "freertos/FreeRTOS.h"
#include "config.h"

typedef enum {
    TRIG_RING_BUTTON = 0,   /* front panel, GPIO4 */
    TRIG_BOOT_BUTTON,       /* onboard BOOT, GPIO0 */
    TRIG_BLE,               /* GATT write 0x01 from the app */
    TRIG_BLE_IDENTIFY,      /* GATT write 0x02: blink the LED, no call */
    TRIG_BLE_NET,           /* GATT write 0x03 from the app: internet call (WhatsApp etc.) */
    TRIG_BLE_TONE,          /* GATT write 0x10 + n (or console :ring n): ringtone n from RINGTONES (config.h) */
    TRIG_SAY,               /* GATT write 0x40 + word numbers (or console :say n n ...): a sentence from the vocabulary */
    TRIG_COUNT
} trigger_src_t;

/* One queued trigger. tone: the ringtone number of a TRIG_BLE_TONE; words: the sentence of a TRIG_SAY. */
typedef struct {
    trigger_src_t src;
    uint8_t tone;
    uint8_t n_words;
    uint8_t words[SAY_MAX_WORDS];
} trigger_t;

void trigger_init(void);
/* Post a trigger from task context (BLE writes). */
void trigger_post(trigger_src_t src);
/* Post ringtone n (task context). Each queued trigger carries its own ringtone number. */
void trigger_post_tone(uint8_t id);
/* Post a sentence (task context): 1..SAY_MAX_WORDS word numbers; more are cut off. */
void trigger_post_say(const uint8_t *words, int n);
/* Block until a trigger arrives; false on timeout. */
bool trigger_wait(trigger_t *t, TickType_t timeout);
/* Drop everything that is queued. */
void trigger_clear(void);
const char *trigger_name(trigger_src_t src);
