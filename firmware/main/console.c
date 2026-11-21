/* AT console: type on the USB serial port, talk to a modem (notes/wiring.md, "AT console").
 *   :d / :a      select the dialer / answerer (DTR on; the Couriers ignore AT with DTR off)
 *   :off         deselect (DTR stays on: idle state), triggers work again
 *   :dtr 0|1     DTR of the selected modem
 *   :dcd         carrier state of the selected modem
 *   :esc         +++ with guard times (back to command mode during a connection)
 *   :tone [hz]   dial tone (default 425 Hz) on the line until :tone off (works without a modem selected)
 *   :play name   play a clip from the sound bank
 *   :ring n      run ringtone n (RINGTONES in config.h), as the app would; no modem may be selected
 *   :say n n ... say the vocabulary words with these numbers (tools/vocab.txt; tools/say.py --print gives the line)
 *   :help
 *   anything else (also an empty line) is sent to the selected modem with CR; its replies print raw. */
#include "console.h"
#include "config.h"
#include "audio.h"
#include "trigger.h"
#include <stdlib.h>

#include <stdio.h>
#include <string.h>
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define CON_UART UART_NUM_0

static modem_t *s_modems[2];
static modem_t *s_sel;               /* selected modem, NULL = none */
static SemaphoreHandle_t s_lock;     /* guards s_sel and s_in_call */
static bool s_in_call;

static void delay_ms(int ms) { vTaskDelay(pdMS_TO_TICKS(ms)); }

static void out(const char *s) { fputs(s, stdout); fflush(stdout); }

static void help(void)
{
    out("\n# AT console: :d dialer, :a answerer, :off release, :dtr 0|1, :dcd, :esc (+++), :tone [hz]|off, :play name, :ring n, :say n n ..., :help\n"
        "# other lines go to the selected modem (an empty line sends CR)\n");
}

static void select_modem(modem_t *m)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_in_call) {
        xSemaphoreGive(s_lock);
        out("# a call is running, try again after it\n");
        return;
    }
    s_sel = m;
    xSemaphoreGive(s_lock);
    if (m) {
        modem_dtr(m, true);
        modem_flush(m);
        printf("# %s selected (buttons/BLE calls paused until :off)\n", m->name);
    } else {
        out("# released, calls enabled (DTR stays on: modems idle ready)\n");
    }
    fflush(stdout);
}

static void command(char *line)
{
    modem_t *m = s_sel;
    if (line[0] != ':') {
        if (!m) { out("# no modem selected (:d or :a)\n"); return; }
        uart_write_bytes(m->uart, line, strlen(line));
        uart_write_bytes(m->uart, "\r", 1);
        return;
    }
    if (!strcmp(line, ":d")) select_modem(s_modems[0]);
    else if (!strcmp(line, ":a")) select_modem(s_modems[1]);
    else if (!strcmp(line, ":off")) {
        if (m) modem_dtr(m, true);       /* idle state is DTR on (in case :dtr 0 was used) */
        select_modem(NULL);
    }
    else if (!strcmp(line, ":help")) help();
    else if (!strcmp(line, ":tone off")) {
        audio_stop();
        out("# tone off (DAC released)\n");
    }
    else if (!strncmp(line, ":tone", 5) && (line[5] == 0 || line[5] == ' ')) {
        int hz = line[5] ? atoi(line + 6) : DIALTONE_HZ;
        if (hz < 50 || hz > 3800) hz = DIALTONE_HZ;
        audio_tone(hz, DIALTONE_LEVEL);
        printf("# tone %d Hz, level %d, until :tone off\n", hz, DIALTONE_LEVEL);
        fflush(stdout);
    }
    else if (!strncmp(line, ":ring ", 6)) {
        if (m) out("# release the modem first (:off)\n");
        else {
            trigger_post_tone((uint8_t)atoi(line + 6));
            printf("# ringtone %d queued\n", atoi(line + 6));
            fflush(stdout);
        }
    }
    else if (!strncmp(line, ":say ", 5)) {
        uint8_t words[SAY_MAX_WORDS];
        int n = 0;
        char *s = line + 5, *end;
        for (; n < SAY_MAX_WORDS; n++, s = end) {
            const long v = strtol(s, &end, 10);
            if (end == s) break;
            words[n] = (uint8_t)v;
        }
        if (m) out("# release the modem first (:off)\n");
        else if (!n) out("# :say needs word numbers\n");
        else {
            trigger_post_say(words, n);
            printf("# sentence of %d word(s) queued\n", n);
            fflush(stdout);
        }
    }
    else if (!strncmp(line, ":play ", 6)) {
        printf(audio_play_name(line + 6) ? "# playing %s\n" : "# no clip %s in the bank\n", line + 6);
        fflush(stdout);
    }
    else if (!m) out("# no modem selected (:d or :a)\n");
    else if (!strcmp(line, ":dtr 1") || !strcmp(line, ":dtr 0")) {
        modem_dtr(m, line[5] == '1');
        printf("# %s DTR %s\n", m->name, line[5] == '1' ? "on" : "off");
        fflush(stdout);
    }
    else if (!strcmp(line, ":dcd")) {
        printf("# %s DCD %s\n", m->name, modem_carrier(m) ? "on (carrier)" : "off");
        fflush(stdout);
    }
    else if (!strcmp(line, ":esc")) {
        delay_ms(T_ESCAPE_GUARD);
        uart_write_bytes(m->uart, "+++", 3);
        delay_ms(T_ESCAPE_GUARD);
        out("# +++ sent\n");
    }
    else out("# unknown, :help\n");
}

static void console_task(void *arg)
{
    char line[128];
    size_t len = 0;
    uint8_t buf[128];
    help();
    for (;;) {
        /* keyboard -> command line */
        int n = uart_read_bytes(CON_UART, buf, sizeof buf, pdMS_TO_TICKS(10));
        for (int i = 0; i < n; i++) {
            const char c = (char)buf[i];
            if (c == '\r' || c == '\n') {
                if (c == '\n' && i > 0 && buf[i - 1] == '\r') continue;   /* CRLF = one line */
                line[len] = '\0';
                len = 0;
                command(line);
            } else if ((c == 0x08 || c == 0x7f) && len) {
                len--;
            } else if (c >= 0x20 && c < 0x7f && len < sizeof line - 1) {
                line[len++] = c;
            }
        }
        /* selected modem -> screen, raw (CR dropped, LF kept) */
        xSemaphoreTake(s_lock, portMAX_DELAY);
        modem_t *m = s_in_call ? NULL : s_sel;
        xSemaphoreGive(s_lock);
        if (!m) continue;
        n = uart_read_bytes(m->uart, buf, sizeof buf, 0);
        if (n <= 0) continue;
        char txt[sizeof buf + 1];
        int k = 0;
        for (int i = 0; i < n; i++)
            if (buf[i] != '\r') txt[k++] = (buf[i] == '\n' || (buf[i] >= 0x20 && buf[i] < 0x7f)) ? (char)buf[i] : '.';
        txt[k] = '\0';
        out(txt);
    }
}

void console_start(modem_t *dialer, modem_t *answerer)
{
    s_modems[0] = dialer;
    s_modems[1] = answerer;
    s_lock = xSemaphoreCreateMutex();
    ESP_ERROR_CHECK(uart_driver_install(CON_UART, 256, 0, 0, NULL, 0));
    uart_vfs_dev_use_driver(CON_UART);   /* printf/ESP_LOG through the driver too, no interleaving bugs */
    xTaskCreate(console_task, "console", 4096, NULL, 3, NULL);
}

bool console_take_modems(void)
{
    if (!s_lock) return true;            /* console not started */
    xSemaphoreTake(s_lock, portMAX_DELAY);
    const bool free = s_sel == NULL;
    if (free) s_in_call = true;
    xSemaphoreGive(s_lock);
    return free;
}

void console_give_modems(void)
{
    if (!s_lock) return;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_in_call = false;
    xSemaphoreGive(s_lock);
}
