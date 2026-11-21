#include "trigger.h"
#include "config.h"

#include <string.h>

#include "driver/gpio.h"
#include "esp_attr.h"
#include "freertos/queue.h"

static QueueHandle_t s_q;               /* of trigger_t */
static TickType_t s_last[TRIG_COUNT];

static void IRAM_ATTR button_isr(void *arg)
{
    trigger_src_t src = (trigger_src_t)(uintptr_t)arg;
    TickType_t now = xTaskGetTickCountFromISR();
    if (now - s_last[src] < pdMS_TO_TICKS(TRIGGER_DEBOUNCE_MS)) return;
    s_last[src] = now;
    BaseType_t woken = pdFALSE;
    const trigger_t item = { .src = src };
    xQueueSendFromISR(s_q, &item, &woken);
    if (woken) portYIELD_FROM_ISR();
}

void trigger_init(void)
{
    s_q = xQueueCreate(8, sizeof(trigger_t));
    const gpio_config_t btn = {
        .pin_bit_mask = (1ULL << PIN_RING_BTN) | (1ULL << PIN_BOOT_BTN),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .intr_type = GPIO_INTR_NEGEDGE,   /* active low */
    };
    ESP_ERROR_CHECK(gpio_config(&btn));
    ESP_ERROR_CHECK(gpio_install_isr_service(0));
    ESP_ERROR_CHECK(gpio_isr_handler_add(PIN_RING_BTN, button_isr, (void *)TRIG_RING_BUTTON));
    ESP_ERROR_CHECK(gpio_isr_handler_add(PIN_BOOT_BTN, button_isr, (void *)TRIG_BOOT_BUTTON));
}

void trigger_post(trigger_src_t src)
{
    const trigger_t item = { .src = src };
    xQueueSend(s_q, &item, 0);
}

void trigger_post_tone(uint8_t id)
{
    const trigger_t item = { .src = TRIG_BLE_TONE, .tone = id };
    xQueueSend(s_q, &item, 0);
}

void trigger_post_say(const uint8_t *words, int n)
{
    if (n < 1) return;
    trigger_t item = { .src = TRIG_SAY, .n_words = (uint8_t)(n > SAY_MAX_WORDS ? SAY_MAX_WORDS : n) };
    memcpy(item.words, words, item.n_words);
    xQueueSend(s_q, &item, 0);
}

bool trigger_wait(trigger_t *t, TickType_t timeout)
{
    return xQueueReceive(s_q, t, timeout) == pdTRUE;
}

void trigger_clear(void)
{
    xQueueReset(s_q);
}

const char *trigger_name(trigger_src_t src)
{
    switch (src) {
    case TRIG_RING_BUTTON: return "RING button";
    case TRIG_BOOT_BUTTON: return "BOOT button";
    case TRIG_BLE: return "BLE";
    case TRIG_BLE_IDENTIFY: return "BLE identify";
    case TRIG_BLE_NET: return "BLE internet call";
    case TRIG_BLE_TONE: return "ringtone";
    case TRIG_SAY: return "say";
    default: return "?";
    }
}
