#include "modem.h"
#include "config.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "modem";

static void delay_ms(int ms) { vTaskDelay(pdMS_TO_TICKS(ms)); }

esp_err_t modem_init(modem_t *m)
{
    const uart_config_t cfg = {
        .baud_rate = MODEM_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,   /* RTS/CTS not wired; &H0&R1 */
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(m->uart, 1024, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(m->uart, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(m->uart, m->tx, m->rx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    /* uart_set_pin() leaves RX without a pull-up (ESP-IDF 5.5.1). Unconnected, GPIO33
     * floated and picked up its own TX from GPIO32 next to it (seen 2026-11-07). */
    ESP_ERROR_CHECK(gpio_pullup_en(m->rx));

#if MODEM_HAS_CTRL_LINES
    /* DTR off (GPIO high) before the pin becomes an output: no glitch. */
    gpio_set_level(m->dtr, 1);
    const gpio_config_t out = {
        .pin_bit_mask = 1ULL << m->dtr,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&out));
    const gpio_config_t in = {
        .pin_bit_mask = 1ULL << m->dcd,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,   /* reads "no carrier" if unwired */
    };
    ESP_ERROR_CHECK(gpio_config(&in));
#endif
    m->len = 0;
    return ESP_OK;
}

void modem_flush(modem_t *m)
{
    uart_flush_input(m->uart);
    m->len = 0;
}

void modem_send(modem_t *m, const char *cmd)
{
    ESP_LOGI(TAG, "%s <- %s", m->name, cmd);
    uart_write_bytes(m->uart, cmd, strlen(cmd));
    uart_write_bytes(m->uart, "\r", 1);
}

static bool all_digits(const char *s)
{
    if (!*s) return false;
    for (; *s; s++) if (!isdigit((unsigned char)*s)) return false;
    return true;
}

static modem_result_t classify(const char *s)
{
    if (!strcmp(s, "OK")) return MR_OK;
    if (!strncmp(s, "CONNECT", 7)) return MR_CONNECT;
    if (!strcmp(s, "RING")) return MR_RING;
    if (!strcmp(s, "NO CARRIER")) return MR_NO_CARRIER;
    if (!strcmp(s, "ERROR")) return MR_ERROR;
    if (!strcmp(s, "NO DIAL TONE")) return MR_NO_DIALTONE;
    if (!strcmp(s, "BUSY")) return MR_BUSY;
    if (!strcmp(s, "NO ANSWER")) return MR_NO_ANSWER;
    if (all_digits(s)) {   /* numeric result codes, in case DIP 2 is set to numeric */
        switch (atoi(s)) {
        case 0: return MR_OK;
        case 2: return MR_RING;
        case 3: return MR_NO_CARRIER;
        case 4: return MR_ERROR;
        case 6: return MR_NO_DIALTONE;
        case 7: return MR_BUSY;
        case 8: return MR_NO_ANSWER;
        default: return MR_CONNECT;   /* 1, 5, 10, 13, ... are CONNECT <speed> */
        }
    }
    return MR_TIMEOUT;   /* echo or informational line */
}

modem_result_t modem_wait(modem_t *m, int timeout_ms)
{
    const int64_t deadline = esp_timer_get_time() + (int64_t)timeout_ms * 1000;
    uint8_t c;
    for (;;) {
        int64_t left_ms = (deadline - esp_timer_get_time()) / 1000;
        if (left_ms < 0) return MR_TIMEOUT;
        if (uart_read_bytes(m->uart, &c, 1, pdMS_TO_TICKS(left_ms > 20 ? 20 : left_ms + 1)) != 1)
            continue;
        if (c == '\r' || c == '\n') {
            if (m->len == 0) continue;
            m->line[m->len] = '\0';
            m->len = 0;
            ESP_LOGI(TAG, "%s -> %s", m->name, m->line);
            modem_result_t r = classify(m->line);
            if (r != MR_TIMEOUT) return r;
        } else if (m->len < sizeof(m->line) - 1 && c >= 0x20 && c < 0x7f) {
            m->line[m->len++] = (char)c;
        }
    }
}

modem_result_t modem_cmd(modem_t *m, const char *cmd, int timeout_ms)
{
    modem_send(m, cmd);
    modem_result_t r = modem_wait(m, timeout_ms);
    if (r != MR_OK) ESP_LOGW(TAG, "%s: %s -> %s", m->name, cmd, modem_result_str(r));
    return r;
}

void modem_unblock(modem_t *m)
{
    modem_send(m, AT_UNBLOCK);
    delay_ms(T_UNBLOCK_SETTLE);
    modem_flush(m);
}

void modem_dtr(modem_t *m, bool on)
{
#if MODEM_HAS_CTRL_LINES
    gpio_set_level(m->dtr, on ? 0 : 1);   /* inverted by the MAX3232 */
#else
    (void)m; (void)on;
#endif
}

bool modem_carrier(const modem_t *m)
{
#if MODEM_HAS_CTRL_LINES
    return gpio_get_level(m->dcd) == 0;   /* inverted by the MAX3232 */
#else
    (void)m;
    return false;
#endif
}

void modem_hangup_all(modem_t **ms, size_t n)
{
#if MODEM_HAS_CTRL_LINES
    for (size_t i = 0; i < n; i++) modem_dtr(ms[i], false);
    delay_ms(T_DTR_DROP);
    /* The caller raises DTR again (ready_modems): idle state is DTR on, modem configured. */
#else
    delay_ms(T_ESCAPE_GUARD);
    for (size_t i = 0; i < n; i++) uart_write_bytes(ms[i]->uart, "+++", 3);
    delay_ms(T_ESCAPE_GUARD);
    for (size_t i = 0; i < n; i++) modem_cmd(ms[i], "ATH0", T_AT_TIMEOUT);
#endif
    for (size_t i = 0; i < n; i++) ESP_LOGI(TAG, "%s hung up", ms[i]->name);
}

const char *modem_result_str(modem_result_t r)
{
    switch (r) {
    case MR_TIMEOUT: return "TIMEOUT";
    case MR_OK: return "OK";
    case MR_CONNECT: return "CONNECT";
    case MR_RING: return "RING";
    case MR_NO_CARRIER: return "NO CARRIER";
    case MR_ERROR: return "ERROR";
    case MR_NO_DIALTONE: return "NO DIAL TONE";
    case MR_BUSY: return "BUSY";
    case MR_NO_ANSWER: return "NO ANSWER";
    }
    return "?";
}
