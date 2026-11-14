#pragma once
#include <stdbool.h>
#include "modem.h"

/* AT console on the USB serial port (UART0, 115200): lines starting with ':' are console commands,
 * anything else goes to the selected modem. Use tools/atcon.py (or idf.py monitor). */
void console_start(modem_t *dialer, modem_t *answerer);
/* The call sequence and the console share the modem UARTs. The main loop takes the modems before
 * a call (false = the console has one selected: skip the call) and gives them back after. */
bool console_take_modems(void);
void console_give_modems(void);
