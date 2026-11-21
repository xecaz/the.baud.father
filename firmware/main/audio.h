#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* Audio on DAC1 (GPIO25) via DMA: 8 kHz, 8-bit unsigned mono.
 * Sources: clips from the "sounds" flash partition (bank built by tools/mksounds.py), or a
 * synthesized sine (the dial tone). One source at a time; a new play/tone replaces the current one.
 * Idle = DAC powered down, pin floating (does not load the line during the handshake).
 * Start and stop ramp the output between 0 V and mid-scale to avoid pops. */

esp_err_t audio_init(void);

int audio_count(void);                 /* clips in the bank (0 if none flashed) */
const char *audio_name(int idx);       /* NULL if out of range */
int audio_find(const char *name);      /* -1 if not found */
int audio_find_prefix(const char *prefix);   /* first clip whose name starts with prefix; -1 if none */
uint32_t audio_len_ms(int idx);

void audio_set_level(int level);      /* clip volume for the next plays, 256 = full scale (default AUDIO_LEVEL) */
bool audio_play(int idx);              /* start a clip; false if idx is invalid */
bool audio_play_name(const char *name);
#define AUDIO_SEQ_MAX 16
/* Clips back to back with gap_ms of silence between them, the DAC stays on throughout. false if n or an idx is invalid. */
bool audio_play_seq(const int *idx, int n, int gap_ms);
void audio_tone(int hz, int level);    /* sine until audio_stop(); level = peak, 1..127 */
void audio_stop(void);                 /* fade out and release the DAC; returns when idle */
bool audio_wait(int timeout_ms);       /* wait until idle (clip finished); false on timeout */
bool audio_busy(void);
