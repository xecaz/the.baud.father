#pragma once
/* Pin map and tunables. Source of truth for pins: notes/wiring.md.
 * Values marked "start" are guesses to tune on the bench (by ear). */

#include "driver/gpio.h"
#include "driver/uart.h"

/* ---- Pins (AZ-Delivery DevKitC-style 38-pin, WROOM-32; header labels = GPIO numbers) ---- */
#define PIN_DIAL_TX     GPIO_NUM_17   /* UART2 */
#define PIN_DIAL_RX     GPIO_NUM_16
#define PIN_DIAL_DTR    GPIO_NUM_18   /* inverted by MAX3232: low = DTR on */
#define PIN_DIAL_DCD    GPIO_NUM_19   /* inverted by MAX3232: low = carrier */
#define PIN_ANS_TX      GPIO_NUM_32   /* UART1, remapped */
#define PIN_ANS_RX      GPIO_NUM_33
#define PIN_ANS_DTR     GPIO_NUM_21
#define PIN_ANS_DCD     GPIO_NUM_22
#define PIN_RING_BTN    GPIO_NUM_4    /* front-panel button to GND, internal pull-up */
#define PIN_BOOT_BTN    GPIO_NUM_0    /* onboard BOOT button */
#define PIN_LED         GPIO_NUM_2
/* Dial tone is DAC channel 0 = GPIO25 (fixed in hardware). */

#define UART_DIAL       UART_NUM_2
#define UART_ANS        UART_NUM_1
#define MODEM_BAUD      115200        /* Couriers autobaud on "AT". At 9600 the link also came up at 9600 (2026-11-14) */

/* 1 = MAX3232 wiring has both channels (DTR + DCD). 0 = TX/RX only:
 * set DIP 1 to DTR override, hang up with +++ / ATH0, detect CONNECT on RX. */
#define MODEM_HAS_CTRL_LINES 1

/* ---- AT strings (CLAUDE.md "Init strings") ---- */
#define AT_DIAL_INIT    "AT&H0&R1M2X3"   /* no flow control, speaker on, no dial-tone wait */
/* Answerer S69 = 11 (as stored) + 32 (disable CTR21 DLG) + 64 (disable loop monitor), runtime only (ATZ restores 11, so
 * it is in the init). Without it a call placed within ~20 s of the previous one failed: the answerer said NO CARRIER
 * 3.2 s after ATA while the dialer was still waiting (3 of 3; with it 3 of 3 connect, 2026-11-14). */
#define AT_ANS_INIT     "AT&H0&R1S69=107"
/* Sent blind (no reply expected) before the probe and after ATZ: a modem with &R2 stored only talks while
 * RTS is on, and RTS is not wired (the first Courier came with &H1&R2 in NVRAM: silent, 2026-11-12). */
#define AT_UNBLOCK      "AT&H0&R1"
#define AT_DIAL_PREFIX  "ATM1DT"         /* speaker on until carrier, tone dial (the V.Everything's NVRAM says DIAL=PULSE) */
/* Digits dialled per trigger (only ever on the closed line). Your own numbers go in main/config_local.h, which is
 * git-ignored:   #define DIAL_DOOR "..."   and   #define DIAL_CALL "..." */
#if __has_include("config_local.h")
#include "config_local.h"
#endif
#ifndef DIAL_DOOR
#define DIAL_DOOR       "0123456789"     /* RING/BOOT buttons */
#endif
#ifndef DIAL_CALL
#define DIAL_CALL       "0123456789"     /* BLE from the app: incoming calls */
#endif
#define AT_ANS_ANSWER   "ATA"

/* ---- Audio (DAC1 = GPIO25 via DMA, audio.c) ---- */
#define AUDIO_RATE_HZ   8000          /* telephone band; the sound bank must match (tools/mksounds.py) */
#define AUDIO_LEVEL     128           /* clip volume, 256 = full scale (start: half) */
#define DIALTONE_HZ     425
#define DIALTONE_LEVEL  64            /* sine peak, 127 = full scale (64 = the old cosine at -6 dB) */
#define AT_CONSOLE      1             /* 1 = AT console on the USB serial port (console.c, tools/atcon.py) */
#define BENCH_TONE      0             /* 1 = bench build: dial tone nonstop from boot, nothing else runs */
/* Clip played per trigger, after off-hook and before the dial tone ("" = none). Names from the bank. */
#define SOUND_BUTTON    "dingdong"
#define SOUND_BLE       "dingdong"
/* Internet calls (WhatsApp etc., BLE 0x03): this clip REPLACES the real handshake ("56k ringtone"): the dialer goes
 * off-hook with the speaker forced on, dial tone, digits, then the clip plays on the line and it hangs up. The
 * answerer is not used. If the clip is not in the bank, an internet call is a normal call. */
#define SOUND_NET_HANDSHAKE "v90"
#define AT_DIAL_PREFIX_NET  "ATM2DT"     /* M2: speaker on while off-hook in command mode (after ';') */
#define T_NET_TAIL           300         /* off-hook this long after the clip, then hang up */

/* ---- Call sequence timing, ms (notes/wiring.md "Call sequence") ---- */
#define T_BOOT_SETTLE       3000   /* let the Couriers power up before AT */
#define T_OFFHOOK_TO_TONE    200   /* ATD sent (off-hook) -> dial tone on (start) */
#define T_FIRST_DIGIT       2150   /* ATD sent -> first DTMF digit (S6 2 s + Courier latency; its echo came at +2156 ms,
                                    * 2026-11-14). The dial tone runs until here; raise it if a gap is heard, lower if they overlap */
#define T_TONE_LEN          (T_FIRST_DIGIT - T_OFFHOOK_TO_TONE)   /* dial tone length */
#define T_TEST_TONE_LEN     1500   /* tone after the clip when no modem answers (bench check) */
#define T_DIAL_TO_ANSWER     200   /* margin after the last digit (dialer-only: after its OK) */
#define T_RINGBACK_PAUSE    1000   /* silence after the last digit (user, 2026-11-14) */
#define T_RINGBACK_LEN      1000   /* then one 425 Hz ringback burst, then the answerer picks up (ATA) */
#define T_S6_WAIT           2000   /* Courier S6: wait before blind dialing (2 s; check ATS6?) */
#define T_DTMF_MS             70   /* Courier S11: DTMF tone and gap length (stored 70) */
#define T_CONNECT_TIMEOUT  40000
#define T_HOLD_AFTER_CONNECT 2000  /* stay connected this long, then hang up (start) */
#define DIALER_ONLY_FALLBACK 1     /* answerer missing: still do off-hook, sound, DTMF on the dialer, then hang up */
#define T_DIAL_ONLY_TIMEOUT 10000  /* "ATD...;" returns OK once the digits are out */
#define T_DIAL_ONLY_HOLD      500  /* stay off-hook this long after the last digit */
#define T_DTR_DROP           600   /* DTR off this long counts as hang-up */
#define T_AT_TIMEOUT        2000
#define T_UNBLOCK_SETTLE     300
#define T_ATZ_SETTLE        1000   /* ATZ (idle time only): reload NVRAM; its OK may be lost if &R2 is stored */
#define T_ESCAPE_GUARD      1200   /* +++ guard time (S12 default is 1 s) */

/* ---- BLE ---- */
#define BLE_DEVICE_NAME     "doorbell"
#define PAIRING_HOLD_MS     3000    /* hold RING/BOOT this long: open the pairing window */
#define FORGET_HOLD_MS     10000    /* keep holding this long: forget all bonded devices */
#define PAIRING_WINDOW_S      60

/* ---- Triggers ---- */
#define TRIGGER_DEBOUNCE_MS    50
#define TRIGGER_RATE_LIMIT_MS 30000   /* ignore triggers this long after a call starts */
#define TRIGGER_RATE_LIMIT_SPEAK_MS 8000   /* same, after a spoken ringtone starts (short: off-hook, clip, hang up) */

/* ---- Ringtones (BLE trigger 0x10 + index, console ":ring n"; notes/ble.md) ----
 * The app maps notifications to an index; the box knows what each one sounds like. Append only: the app stores indexes.
 *   RT_CALL   the normal call: dial tone, digits, ringback, real handshake (dialer-only without the answerer)
 *   RT_CLIP   as RT_CALL, but the clip replaces the handshake (dialer only; the old 0x03 "56k" ring)
 *   RT_SPEAK  the dialer lifts the line (speaker on), the clip plays, it hangs up. No dialing.
 *   RT_DEMO   a normal call (dial, 33.6k connect), then the spoken ringtones in DEMO_SPEAK, T_DEMO_PAUSE before each
 *   RT_FAIL   a call whose handshake is jammed by a tone for T_JAM and given up, then a normal call (redial, connects) */
typedef enum { RT_CALL, RT_CLIP, RT_SPEAK, RT_FAIL, RT_DEMO } ringtone_kind_t;
typedef struct { const char *name; ringtone_kind_t kind; const char *clip; } ringtone_t;
#define RINGTONES { \
    { "call",     RT_CALL,  ""         },   /* 0 */ \
    { "56k clip", RT_CLIP,  "v90"      },   /* 1 */ \
    { "whatsapp", RT_SPEAK, "whatsapp" },   /* 2: "WhatsApp message" (firmware/sounds/whatsapp.wav) */ \
    { "signal",   RT_SPEAK, "signal"   },   /* 3: "Signal message"   (firmware/sounds/signal.wav) */ \
    { "failed call", RT_FAIL, ""       },   /* 4: failed negotiation, redial, connect */ \
    { "email",    RT_SPEAK, "email"    },   /* 5: "Incoming email" (firmware/sounds/email.wav) */ \
    { "demo",     RT_DEMO,  ""         },   /* 6: call + connect, "Signal message", "WhatsApp message" (user, 2026-11-14) */ \
}
/* What the old trigger bytes ring (app 0.4): 0x01 = a regular phone call, 0x03 = an internet call (user, 2026-11-14:
 * phone = the long failed negotiation, WhatsApp call = a real 33.6k connect). The RING/BOOT buttons stay a normal call. */
#define RINGTONE_BLE_CALL    4
#define RINGTONE_BLE_NET     0
#define JAM_HZ               1750        /* in the V.8 answer band (JM, 1650/1850 Hz): the modems cannot agree while it sounds */
#define JAM_LEVEL            DIALTONE_LEVEL
#define T_JAM                20000       /* ms of jammed handshake before giving up (start; by ear) */
#define T_REDIAL_PAUSE       1500        /* extra pause before the redial (the modems' reset adds ~4.5 s) */
#define DEMO_SPEAK           { 3, 2 }    /* ringtone numbers spoken after the demo call: signal, whatsapp */
#define T_DEMO_PAUSE         1000        /* hang-up -> first voice, and between the voices (one off-hook for all) */
#define SOUND_SPEAK_FALLBACK "dingdong"   /* played when a spoken ringtone's clip is not in the bank */
#define SPEAK_LEVEL          256         /* clip volume for spoken ringtones (AUDIO_LEVEL was "a bit low", 2026-11-14) */
#define AT_SPEAK_OFFHOOK     "ATM2H1"     /* off-hook in command mode, speaker on */
#define T_SPEAK_LEAD          400         /* off-hook click -> clip */
#define T_SPEAK_TAIL          300         /* clip end -> hang up */
