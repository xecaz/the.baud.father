/* modem.doorbell: trigger -> off-hook click -> 425 Hz dial tone -> DTMF -> handshake -> hang up.
 * Design B (notes/wiring.md): the ESP32 drives both Couriers over RS232.
 * Triggers: RING/BOOT buttons (short press) and BLE (notes/ble.md).
 * Audio (clips and the dial tone) goes out on the DAC, see audio.c. */
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "ble.h"
#include "config.h"
#include "audio.h"
#include "console.h"
#include "modem.h"
#include "trigger.h"

#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

static const char *TAG = "doorbell";

static modem_t s_dialer = {
    .name = "dialer", .uart = UART_DIAL,
    .tx = PIN_DIAL_TX, .rx = PIN_DIAL_RX, .dtr = PIN_DIAL_DTR, .dcd = PIN_DIAL_DCD,
};
static modem_t s_answerer = {
    .name = "answerer", .uart = UART_ANS,
    .tx = PIN_ANS_TX, .rx = PIN_ANS_RX, .dtr = PIN_ANS_DTR, .dcd = PIN_ANS_DCD,
};
static modem_t *s_both[] = { &s_dialer, &s_answerer };

static void delay_ms(int ms) { vTaskDelay(pdMS_TO_TICKS(ms)); }
static int64_t now_ms(void) { return esp_timer_get_time() / 1000; }

/* ---------------- LED ---------------- */

static esp_timer_handle_t s_blink_timer;
static bool s_blinking;

static void led(bool on) { gpio_set_level(PIN_LED, on); }

static void blink_cb(void *arg)
{
    static bool on;
    on = !on;
    led(on);
}

static void led_blink(bool enable)
{
    if (enable && !s_blinking) esp_timer_start_periodic(s_blink_timer, 150 * 1000);
    if (!enable && s_blinking) {
        esp_timer_stop(s_blink_timer);
        led(false);
    }
    s_blinking = enable;
}

static void led_init(void)
{
    gpio_reset_pin(PIN_LED);
    gpio_set_direction(PIN_LED, GPIO_MODE_OUTPUT);
    led(false);
    const esp_timer_create_args_t args = { .callback = blink_cb, .name = "blink" };
    ESP_ERROR_CHECK(esp_timer_create(&args, &s_blink_timer));
    for (int i = 0; i < 2; i++) {   /* boot flash: shows the LED works */
        led(true);
        delay_ms(100);
        led(false);
        delay_ms(100);
    }
}

/* "Identify" from the app: 3 short flashes. */
static void led_identify(void)
{
    for (int i = 0; i < 3; i++) {
        led(true);
        delay_ms(150);
        led(false);
        delay_ms(150);
    }
}

/* ---------------- Call sequence ---------------- */

/* Idle state: DTR on (TR lit), on hook, configured, waiting for a dial or ATA. ATH0 + ATZ happen here, in
 * idle time, so a trigger only costs the dial command; the blind AT&H0&R1 covers a stored &R2. */
static bool s_ready[2];

static bool modem_ready(modem_t *m, const char *init)
{
    modem_dtr(m, true);
    delay_ms(100);
    modem_flush(m);
    modem_unblock(m);
    /* Clean start in idle time (not at the trigger): on hook, NVRAM reloaded. A reset mid-call left the
     * dialer OFF HOOK, and a second dial after a dialer-only call was silent without ATZ (2026-11-12). */
    modem_send(m, "ATH0");
    delay_ms(T_UNBLOCK_SETTLE);
    modem_send(m, "ATZ");
    delay_ms(T_ATZ_SETTLE);
    modem_unblock(m);
    return modem_cmd(m, init, T_AT_TIMEOUT) == MR_OK;
}

/* Both modems, the same steps as modem_ready() but side by side: one set of settle times instead of two
 * (about 2.1 s instead of 4.4 s after every call). */
static void ready_modems(void)
{
    static const char *const init[2] = { AT_DIAL_INIT, AT_ANS_INIT };
    for (size_t i = 0; i < 2; i++) modem_dtr(s_both[i], true);
    delay_ms(100);
    for (size_t i = 0; i < 2; i++) { modem_flush(s_both[i]); modem_send(s_both[i], AT_UNBLOCK); }
    delay_ms(T_UNBLOCK_SETTLE);
    for (size_t i = 0; i < 2; i++) { modem_flush(s_both[i]); modem_send(s_both[i], "ATH0"); }
    delay_ms(T_UNBLOCK_SETTLE);
    for (size_t i = 0; i < 2; i++) modem_send(s_both[i], "ATZ");
    delay_ms(T_ATZ_SETTLE);
    for (size_t i = 0; i < 2; i++) modem_send(s_both[i], AT_UNBLOCK);
    delay_ms(T_UNBLOCK_SETTLE);
    for (size_t i = 0; i < 2; i++) modem_flush(s_both[i]);
    for (size_t i = 0; i < 2; i++) s_ready[i] = modem_cmd(s_both[i], init[i], T_AT_TIMEOUT) == MR_OK;
    ESP_LOGI(TAG, "modems: dialer %s, answerer %s", s_ready[0] ? "ready" : "not responding",
             s_ready[1] ? "ready" : "not responding (dialer-only calls)");
}

/* Wait for the handshake to finish: CONNECT on either side, or DCD on the dialer. */
static modem_result_t wait_connect(int timeout_ms)
{
    const int64_t deadline = now_ms() + timeout_ms;
    while (now_ms() < deadline) {
        if (modem_carrier(&s_dialer)) {
            ESP_LOGI(TAG, "dialer DCD on");
            return MR_CONNECT;
        }
        for (size_t i = 0; i < 2; i++) {
            modem_result_t r = modem_wait(s_both[i], 50);
            if (r == MR_CONNECT) return MR_CONNECT;
            if (r != MR_TIMEOUT && r != MR_OK && r != MR_RING) return r;   /* NO CARRIER etc. */
        }
    }
    return MR_TIMEOUT;
}

/* "ATM1DT555" etc.; ';' appended for a dialer-only call (back to command mode after the digits). */
static bool is_ble(trigger_src_t src) { return src == TRIG_BLE || src == TRIG_BLE_NET; }

static const char *digits_for(trigger_src_t src) { return is_ble(src) ? DIAL_CALL : DIAL_DOOR; }

static void dial_cmd(char *buf, size_t len, const char *prefix, trigger_src_t src, bool semicolon)
{
    snprintf(buf, len, "%s%s%s", prefix, digits_for(src), semicolon ? ";" : "");
}

static const char *sound_for(trigger_src_t src)
{
    return is_ble(src) ? SOUND_BLE : SOUND_BUTTON;
}

/* The trigger's clip (if any, and if it is in the bank), played to the end. */
static void play_trigger_sound(trigger_src_t src)
{
    const char *name = sound_for(src);
    if (!name[0] || !audio_play_name(name)) return;
    audio_wait(-1);
}

/* After the last digit: silence, then one 425 Hz ringback burst (like the far end ringing once). */
static void ringback(void)
{
    delay_ms(T_RINGBACK_PAUSE);
    audio_tone(DIALTONE_HZ, DIALTONE_LEVEL);
    delay_ms(T_RINGBACK_LEN);
    audio_stop();
}

static const ringtone_t s_ringtones[] = RINGTONES;
#define N_RINGTONES ((int)(sizeof s_ringtones / sizeof s_ringtones[0]))

static bool ringtone_is_short(int id)
{
    return id >= 0 && id < N_RINGTONES && s_ringtones[id].kind == RT_SPEAK;
}

/* ---------------- Pending rings ----------------
 * Triggers wait here until the box can play them (config.h "Triggers"). Only the main task touches the list.
 * Two kinds: spoken ringtones ("messages": short, several fit in one off-hook) and everything else ("calls"). */
typedef struct { trigger_src_t src; uint8_t tone; int64_t at; } pend_t;
static pend_t s_pend[PEND_MAX];
static int s_pend_n;
static int64_t s_spoken_at[N_RINGTONES];   /* last start of each spoken ringtone (0 = never) */
static int64_t s_call_not_before;          /* earliest start of the next call */

static bool pend_is_spoken(const pend_t *p) { return p->src == TRIG_BLE_TONE && ringtone_is_short(p->tone); }

static void pend_remove(int i)
{
    memmove(&s_pend[i], &s_pend[i + 1], (size_t)(s_pend_n - i - 1) * sizeof s_pend[0]);
    s_pend_n--;
}

/* First waiting message (spoken = true) or call (false); -1 if none. */
static int pend_find(bool spoken)
{
    for (int i = 0; i < s_pend_n; i++) if (pend_is_spoken(&s_pend[i]) == spoken) return i;
    return -1;
}

static void pend_add(trigger_src_t src, uint8_t tone)
{
    if (src == TRIG_BLE)     { src = TRIG_BLE_TONE; tone = RINGTONE_BLE_CALL; }   /* 0x01: a regular phone call */
    if (src == TRIG_BLE_NET) { src = TRIG_BLE_TONE; tone = RINGTONE_BLE_NET; }    /* 0x03: an internet call */
    const pend_t p = { .src = src, .tone = tone, .at = now_ms() };
    char what[24];
    if (src == TRIG_BLE_TONE) snprintf(what, sizeof what, "ringtone %d", tone);
    else snprintf(what, sizeof what, "%s", trigger_name(src));

    if (pend_is_spoken(&p)) {
        for (int i = 0; i < s_pend_n; i++) {
            if (pend_is_spoken(&s_pend[i]) && s_pend[i].tone == tone) {
                ESP_LOGI(TAG, "trigger: %s ignored (already waiting)", what);
                return;
            }
        }
        if (s_spoken_at[tone] && p.at - s_spoken_at[tone] < TRIGGER_SPEAK_REPEAT_MS) {
            ESP_LOGI(TAG, "trigger: %s ignored (said %lld s ago)", what, (p.at - s_spoken_at[tone]) / 1000);
            return;
        }
    } else if (pend_find(false) >= 0) {
        ESP_LOGI(TAG, "trigger: %s ignored (a call is already waiting)", what);
        return;
    }
    if (s_pend_n >= PEND_MAX) {
        ESP_LOGW(TAG, "trigger: %s ignored (%d rings waiting)", what, s_pend_n);
        return;
    }
    s_pend[s_pend_n++] = p;
    ESP_LOGI(TAG, "trigger: %s (%d waiting)", what, s_pend_n);
}

static void pend_expire(void)
{
    const int64_t now = now_ms();
    for (int i = s_pend_n - 1; i >= 0; i--) {
        if (now - s_pend[i].at <= PEND_MAX_AGE_MS) continue;
        ESP_LOGW(TAG, "a waiting ring (%s %d) is %lld s old: dropped", trigger_name(s_pend[i].src), s_pend[i].tone,
                 (now - s_pend[i].at) / 1000);
        pend_remove(i);
    }
}

/* Move what arrived during a ring from the trigger queue to the list. Buttons and identify are not kept: a press
 * during a ring does not queue a second one. */
static void collect_triggers(void)
{
    trigger_src_t src;
    uint8_t tone;
    while (trigger_wait(&src, &tone, 0)) {
        if (src == TRIG_BLE || src == TRIG_BLE_NET || src == TRIG_BLE_TONE) pend_add(src, tone);
        else ESP_LOGI(TAG, "%s ignored (busy)", trigger_name(src));
    }
}

static void speak_pending(bool after_call);

/* > 0: the next call is a failed negotiation. A tone on the line keeps the modems from agreeing (they keep trying,
 * measured 2026-11-14: 30 s of 1750 Hz, no connect; 33.6k within 6 s once it stopped); after this long, hang up. */
static int s_jam_ms;
/* true: after the call only hang up, skip the modem reset (the demo speaks right after; it resets at its end). */
static bool s_quick_end;

static void run_call(trigger_src_t src)
{
    led(true);
    const int64_t t0 = now_ms();

    if (!s_ready[0]) s_ready[0] = modem_ready(&s_dialer, AT_DIAL_INIT);   /* plugged in since boot? */
    if (!s_ready[0]) {
        /* Bench aid: no dialer, so play the clip and the tone to check GPIO25. */
        ESP_LOGE(TAG, "dialer not responding; playing the clip and a %d ms test tone instead", T_TEST_TONE_LEN);
        play_trigger_sound(src);
        audio_tone(DIALTONE_HZ, DIALTONE_LEVEL);
        delay_ms(T_TEST_TONE_LEN);
        goto out;
    }
    /* Internet call with the 56k clip in the bank: the clip replaces the handshake (dialer only). */
    const bool fake = src == TRIG_BLE_NET && audio_find(SOUND_NET_HANDSHAKE) >= 0;
    if (src == TRIG_BLE_NET && !fake)
        ESP_LOGW(TAG, "clip \"%s\" not in the bank: internet call rings like a normal call", SOUND_NET_HANDSHAKE);
    const bool full = s_ready[1] && !fake;           /* answerer there: handshake; else dialer-only */
    const char *digits = digits_for(src);
    char dial[48];
    dial_cmd(dial, sizeof dial, fake ? AT_DIAL_PREFIX_NET : AT_DIAL_PREFIX, src, !full);

    /* ATD goes off-hook itself (the click) and waits S6 before the digits: the dial tone plays in that gap,
     * like a real phone. */
    modem_flush(&s_dialer);
    modem_send(&s_dialer, dial);
    delay_ms(T_OFFHOOK_TO_TONE);
    audio_tone(DIALTONE_HZ, DIALTONE_LEVEL);         /* on the line via the transformer (once wired) */
    delay_ms(T_TONE_LEN);
    audio_stop();                                    /* DAC off: does not load the line */

    if (!full) {
        modem_result_t r = modem_wait(&s_dialer, T_DIAL_ONLY_TIMEOUT);   /* OK once the digits are out (;) */
        ESP_LOGI(TAG, "dialer-only %s: %s after %lld ms", digits, modem_result_str(r), now_ms() - t0);
        ringback();
        if (fake) {   /* still off-hook, speaker on (M2): the 56k handshake comes from the clip */
            ESP_LOGI(TAG, "playing \"%s\" as the handshake", SOUND_NET_HANDSHAKE);
            audio_play_name(SOUND_NET_HANDSHAKE);
            audio_wait(-1);
            audio_stop();
            delay_ms(T_NET_TAIL);
        } else {
            delay_ms(T_DIAL_ONLY_HOLD);
        }
        modem_cmd(&s_dialer, "ATH0", T_AT_TIMEOUT);   /* on hook now, before the DTR drop as well */
        goto out;
    }

    /* The digits run from T_FIRST_DIGIT (where the dial tone just stopped): each is tone + gap (S11 each).
     * Then a pause, one ringback burst, and the answerer picks up. */
    const int digits_left = T_FIRST_DIGIT + (int)strlen(digits) * 2 * T_DTMF_MS + T_DIAL_TO_ANSWER
                            - T_OFFHOOK_TO_TONE - T_TONE_LEN;
    if (digits_left > 0) delay_ms(digits_left);
    ringback();
    modem_send(&s_answerer, AT_ANS_ANSWER);          /* answer tone, handshake */

    modem_result_t r;
    if (s_jam_ms > 0) {
        audio_tone(JAM_HZ, JAM_LEVEL);
        r = wait_connect(s_jam_ms);
        audio_stop();
        ESP_LOGI(TAG, "jammed handshake (%d Hz, %d ms): %s after %lld ms", JAM_HZ, s_jam_ms,
                 r == MR_TIMEOUT ? "no connect, giving up" : modem_result_str(r), now_ms() - t0);
        goto out;
    }
    r = wait_connect(T_CONNECT_TIMEOUT);
    if (r != MR_CONNECT) {   /* diagnosis: was the dialer still off-hook waiting for a carrier? (any byte aborts: NO CARRIER) */
        modem_result_t d = modem_cmd(&s_dialer, "AT", T_AT_TIMEOUT);
        ESP_LOGW(TAG, "after the failure the dialer says %s to AT (NO CARRIER = it was still waiting; OK = it had already hung up)",
                 modem_result_str(d));
    }
    ESP_LOGI(TAG, "handshake result: %s after %lld ms", modem_result_str(r), now_ms() - t0);
    if (r == MR_CONNECT) delay_ms(T_HOLD_AFTER_CONNECT);

out:
    audio_stop();      /* in case we jumped here mid-tone */
    modem_hangup_all(s_both, 2);
    if (!s_quick_end) {
        collect_triggers();
        speak_pending(true);             /* messages that came in during the call: said now, before the reset */
        ready_modems();                  /* back to idle: DTR on, configured; also picks up a modem connected since */
    }
    led(false);
}

/* Spoken clips: the dialer lifts the line with the speaker on (speak_open), clips play (speak_clip), it hangs up
 * (speak_close). Dialer only, no dialing. Without a dialer the clips still play on the DAC. */
static bool s_speak_line;

static void speak_open(void)
{
    led(true);
    if (!s_ready[0]) s_ready[0] = modem_ready(&s_dialer, AT_DIAL_INIT);
    s_speak_line = s_ready[0];
    if (!s_speak_line) {
        ESP_LOGE(TAG, "dialer not responding; playing the clip on the DAC only");
        return;
    }
    modem_flush(&s_dialer);
    modem_result_t r = modem_cmd(&s_dialer, AT_SPEAK_OFFHOOK, T_AT_TIMEOUT);
    ESP_LOGI(TAG, "speak: off-hook %s", modem_result_str(r));
    delay_ms(T_SPEAK_LEAD);
}

static void speak_clip(const char *clip)
{
    if (audio_find(clip) < 0) {
        ESP_LOGW(TAG, "clip \"%s\" not in the bank: playing \"%s\"", clip, SOUND_SPEAK_FALLBACK);
        clip = SOUND_SPEAK_FALLBACK;
    }
    audio_set_level(SPEAK_LEVEL);
    if (audio_play_name(clip)) audio_wait(-1);
    audio_stop();
    audio_set_level(AUDIO_LEVEL);
}

static void speak_close(void)
{
    if (s_speak_line) {
        delay_ms(T_SPEAK_TAIL);
        modem_cmd(&s_dialer, "ATH0", T_AT_TIMEOUT);
        modem_cmd(&s_dialer, AT_DIAL_INIT, T_AT_TIMEOUT);   /* back to the idle settings */
    }
    led(false);
}

static void run_speak(const ringtone_t *rt)
{
    speak_open();
    speak_clip(rt->clip);
    speak_close();
}

/* Right after a DTR hang-up: DTR back on (the Courier ignores AT without it), then the rest of T_DEMO_PAUSE
 * (off-hook and T_SPEAK_LEAD follow in speak_open). */
static void speak_after_hangup(void)
{
    modem_dtr(&s_dialer, true);
    modem_flush(&s_dialer);
    delay_ms(T_DEMO_PAUSE > T_SPEAK_LEAD + 300 ? T_DEMO_PAUSE - T_SPEAK_LEAD - 300 : 0);
}

/* Say every waiting message in one off-hook, including the ones that arrive meanwhile. after_call: called from
 * run_call() between the hang-up and the modem reset. Otherwise (idle) a call that becomes due ends the round:
 * calls go first, the rest is said after its hang-up. */
static void speak_pending(bool after_call)
{
    pend_expire();
    if (pend_find(true) < 0) return;
    if (after_call) speak_after_hangup();
    speak_open();
    for (int n = 0, i; (i = pend_find(true)) >= 0; n++) {
        const int id = s_pend[i].tone;
        pend_remove(i);
        if (n) delay_ms(T_SPEAK_GAP);
        ESP_LOGI(TAG, "ringtone %d \"%s\"%s", id, s_ringtones[id].name, after_call ? " (after the call)" : "");
        s_spoken_at[id] = now_ms();
        speak_clip(s_ringtones[id].clip);
        collect_triggers();
        pend_expire();
        if (!after_call && pend_find(false) >= 0 && now_ms() + T_SPEAK_TO_CALL >= s_call_not_before) break;
    }
    speak_close();
    if (s_call_not_before < now_ms() + T_SPEAK_TO_CALL) s_call_not_before = now_ms() + T_SPEAK_TO_CALL;
}

/* Ringtone n from the table. Unknown numbers ring like a normal BLE call. */
static void run_ringtone(int id)
{
    if (id < 0 || id >= N_RINGTONES) {
        ESP_LOGW(TAG, "ringtone %d unknown (%d defined): normal call", id, N_RINGTONES);
        run_call(TRIG_BLE);
        return;
    }
    const ringtone_t *rt = &s_ringtones[id];
    ESP_LOGI(TAG, "ringtone %d \"%s\"", id, rt->name);
    switch (rt->kind) {
    case RT_SPEAK: run_speak(rt); break;
    case RT_DEMO: {                                 /* a call that connects, then the spoken ones */
        static const uint8_t say[] = DEMO_SPEAK;
        s_quick_end = true;
        run_call(TRIG_BLE);
        s_quick_end = false;
        speak_after_hangup();
        speak_open();                               /* one off-hook for all the clips: the pauses stay exact */
        for (size_t i = 0; i < sizeof say; i++) {
            if (i) delay_ms(T_DEMO_PAUSE);
            if (say[i] < N_RINGTONES && s_ringtones[say[i]].kind == RT_SPEAK) speak_clip(s_ringtones[say[i]].clip);
        }
        speak_close();
        ready_modems();
        break;
    }
    case RT_FAIL:                                   /* struggle, give up, redial, connect */
        if (s_ready[1]) {                           /* needs the answerer; without it: one normal (dialer-only) call */
            s_jam_ms = T_JAM;
            run_call(TRIG_BLE);
            s_jam_ms = 0;
            delay_ms(T_REDIAL_PAUSE);
        }
        run_call(TRIG_BLE);
        break;
    case RT_CLIP:  run_call(TRIG_BLE_NET); break;   /* clip = SOUND_NET_HANDSHAKE for now */
    default:       run_call(TRIG_BLE); break;
    }
}

#if MODEM_HAS_CTRL_LINES
/* Bench check of the control lines: toggle DTR and read DCD back. With DB9 1-4 shorted (loopback)
 * DCD must follow DTR. With a modem attached DCD shows its carrier instead (normally off at boot). */
static void line_test(modem_t *m)
{
    modem_dtr(m, false);
    delay_ms(50);
    const bool dcd_off = modem_carrier(m);
    modem_dtr(m, true);
    delay_ms(50);
    const bool dcd_on = modem_carrier(m);
    modem_dtr(m, false);
    const char *verdict =
        ( dcd_on && !dcd_off) ? "DCD follows DTR (DB9 1-4 loopback OK)" :
        (!dcd_on && !dcd_off) ? "DCD stays off (no loopback; with a modem: no carrier, normal)" :
        ( dcd_on &&  dcd_off) ? "DCD stays on (modem with &C0, or the DCD line is stuck)" :
                                "DCD inverted (check the wiring)";
    ESP_LOGI(TAG, "%s DTR/DCD: DTR off -> DCD %s, DTR on -> DCD %s: %s", m->name,
             dcd_off ? "on" : "off", dcd_on ? "on" : "off", verdict);
}
#endif

/* At boot: control-line check, then both modems configured and left ready (DTR on). */
static void probe_modems(void)
{
#if MODEM_HAS_CTRL_LINES
    for (size_t i = 0; i < 2; i++) line_test(s_both[i]);
#endif
    ready_modems();
}

/* ---------------- Buttons: short press / pairing / forget ---------------- */

typedef enum { PRESS_NOISE, PRESS_SHORT, PRESS_PAIR, PRESS_FORGET } press_t;
#define PRESS_MIN_MS 30   /* shorter = contact bounce (a "held 1 ms" press started a call, 2026-11-07) */

/* Called right after the falling edge; returns once the button is released.
 * Released = read "up" for RELEASE_STABLE_MS without a break: the first reading right after
 * the edge can catch contact bounce, which made long holds count as short presses (seen
 * 2026-11-07: hold registered as "trigger: BOOT button"). */
#define RELEASE_STABLE_MS 50
static press_t measure_press(gpio_num_t pin)
{
    const int64_t t0 = now_ms();
    int64_t held = 0, up_since = -1;
    bool forget_shown = false;
    for (;;) {
        int64_t t = now_ms();
        if (gpio_get_level(pin) == 0) {
            up_since = -1;
        } else {
            if (up_since < 0) up_since = t;
            if (t - up_since >= RELEASE_STABLE_MS) break;
        }
        held = (up_since < 0 ? t : up_since) - t0;
        if (held >= PAIRING_HOLD_MS) led_blink(true);           /* "you can let go now" */
        if (held >= FORGET_HOLD_MS && !forget_shown) {
            led_blink(false);
            led(true);                                          /* solid: bonds will be cleared */
            forget_shown = true;
        }
        delay_ms(10);
    }
    ESP_LOGI(TAG, "button held %lld ms", held);
    if (held >= FORGET_HOLD_MS) return PRESS_FORGET;
    if (held >= PAIRING_HOLD_MS) return PRESS_PAIR;
    if (held < PRESS_MIN_MS) return PRESS_NOISE;
    return PRESS_SHORT;
}

/* ---------------- Main loop ---------------- */

void app_main(void)
{
    esp_err_t err = nvs_flash_init();   /* BLE bonds live in NVS */
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    led_init();
    ESP_ERROR_CHECK(modem_init(&s_dialer));
    ESP_ERROR_CHECK(modem_init(&s_answerer));
    ESP_ERROR_CHECK(audio_init());      /* also pins the 8 MHz clock BT needs, see audio.c */
#if BENCH_TONE
    ESP_LOGW(TAG, "BENCH_TONE build: %d Hz, level %d, nonstop (no BLE, no buttons, no modems)",
             DIALTONE_HZ, DIALTONE_LEVEL);
    audio_tone(DIALTONE_HZ, DIALTONE_LEVEL);
    for (;;) delay_ms(1000);
#endif
    trigger_init();                     /* queue before BLE: GATT writes post into it */
    ESP_ERROR_CHECK(ble_init());

    ESP_LOGI(TAG, "waiting %d ms for the modems to power up", T_BOOT_SETTLE);
    delay_ms(T_BOOT_SETTLE);
    probe_modems();
#if AT_CONSOLE
    console_start(&s_dialer, &s_answerer);
#endif
    ESP_LOGI(TAG, "ready: short press RING/BOOT = call, hold %d s = pairing, hold %d s = forget bonds",
             PAIRING_HOLD_MS / 1000, FORGET_HOLD_MS / 1000);

    bool waiting = false;   /* Status shows "a ring is waiting" */
    bool pairing = false;
    for (;;) {
        trigger_src_t src;
        uint8_t tone = 0;
        bool got = trigger_wait(&src, &tone, pdMS_TO_TICKS(s_pend_n ? 50 : 250));

        /* Housekeeping: Bluetooth health, expire the pairing window. */
        if (ble_is_stuck()) {
            ESP_LOGE(TAG, "Bluetooth is stuck: restarting");
            vTaskDelay(pdMS_TO_TICKS(200));
            esp_restart();
        }
        if (pairing && !ble_pairing_is_open()) {
            pairing = false;
            ble_pairing_close();
            led_blink(false);
            ble_set_status(waiting ? BLE_STATUS_COOLDOWN : BLE_STATUS_IDLE);
        }

        if (got && src == TRIG_BLE_IDENTIFY) {
            if (!pairing) led_identify();
            got = false;
        }
        if (got && (src == TRIG_RING_BUTTON || src == TRIG_BOOT_BUTTON)) {
            press_t p = measure_press(src == TRIG_RING_BUTTON ? PIN_RING_BTN : PIN_BOOT_BTN);
            if (p == PRESS_FORGET) {
                ble_forget_all();
                ble_pairing_close();
                pairing = false;
                delay_ms(1000);
                led(false);
                trigger_clear();
                s_pend_n = 0;
                waiting = false;
                ble_set_status(BLE_STATUS_IDLE);
            } else if (p == PRESS_PAIR) {
                ble_pairing_open(PAIRING_WINDOW_S);
                pairing = true;
                ble_set_status(BLE_STATUS_PAIRING);
                trigger_clear();
            }
            if (p != PRESS_SHORT) got = false;
        }
        if (got) pend_add(src, tone);

        /* What to play now: a call that is due goes first, else the waiting messages. A call inside the gap
         * after the previous one waits (Status "cooldown"). */
        pend_expire();
        const int call = pend_find(false);
        const bool call_due = call >= 0 && now_ms() >= s_call_not_before;
        if (!call_due && pend_find(true) < 0) {
            if (waiting != (s_pend_n > 0)) {
                waiting = s_pend_n > 0;
                if (!pairing) ble_set_status(waiting ? BLE_STATUS_COOLDOWN : BLE_STATUS_IDLE);
            }
            continue;
        }
        if (!console_take_modems()) {
            ESP_LOGW(TAG, "%d ring(s) ignored: the AT console has a modem selected (type :off)", s_pend_n);
            s_pend_n = 0;
            continue;
        }
        if (pairing) {   /* a ring ends the pairing window */
            pairing = false;
            ble_pairing_close();
            led_blink(false);
        }
        ble_set_status(BLE_STATUS_CALLING);
        if (call_due) {
            const pend_t p = s_pend[call];
            pend_remove(call);
            if (p.src == TRIG_BLE_TONE) run_ringtone(p.tone);
            else run_call(p.src);
            s_call_not_before = now_ms() + TRIGGER_CALL_GAP_MS;
        } else {
            speak_pending(false);
        }
        console_give_modems();
        collect_triggers();   /* arrived during the last steps: next round */
        waiting = s_pend_n > 0;
        ble_set_status(waiting ? BLE_STATUS_COOLDOWN : BLE_STATUS_IDLE);
    }
}
