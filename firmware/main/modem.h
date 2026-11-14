#pragma once
#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"
#include "driver/gpio.h"
#include "driver/uart.h"

typedef enum {
    MR_TIMEOUT = 0,
    MR_OK,
    MR_CONNECT,
    MR_RING,
    MR_NO_CARRIER,
    MR_ERROR,
    MR_NO_DIALTONE,
    MR_BUSY,
    MR_NO_ANSWER,
} modem_result_t;

typedef struct {
    const char *name;
    uart_port_t uart;
    gpio_num_t tx, rx, dtr, dcd;
    char line[160];   /* current RX line being assembled */
    size_t len;
} modem_t;

esp_err_t modem_init(modem_t *m);
void modem_flush(modem_t *m);
/* Send a command; "\r" is appended. */
void modem_send(modem_t *m, const char *cmd);
/* Wait for the next result code (echo and other lines are logged and skipped). */
modem_result_t modem_wait(modem_t *m, int timeout_ms);
/* Send and wait for the result code. */
modem_result_t modem_cmd(modem_t *m, const char *cmd, int timeout_ms);
/* Send AT_UNBLOCK without waiting for a reply (it may not come), then drop whatever did come. */
void modem_unblock(modem_t *m);
void modem_dtr(modem_t *m, bool on);
bool modem_carrier(const modem_t *m);
/* Hang up all given modems at once (DTR drop, or +++/ATH0 fallback). */
void modem_hangup_all(modem_t **ms, size_t n);
const char *modem_result_str(modem_result_t r);
