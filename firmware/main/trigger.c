#include "trigger.h"
#include "config.h"

#include "driver/gpio.h"
#include "esp_attr.h"
#include "freertos/queue.h"

/* Queue item: source in the low byte, ringtone number in the high byte. */
static QueueHandle_t s_q;
static TickType_t s_last[TRIG_COUNT];

static void IRAM_ATTR button_isr(void *arg)
{
    trigger_src_t src = (trigger_src_t)(uintptr_t)arg;
    TickType_t now = xTaskGetTickCountFromISR();
    if (now - s_last[src] < pdMS_TO_TICKS(TRIGGER_DEBOUNCE_MS)) return;
    s_last[src] = now;
    BaseType_t woken = pdFALSE;
    const uint16_t item = (uint16_t)src;
    xQueueSendFromISR(s_q, &item, &woken);
    if (woken) portYIELD_FROM_ISR();
}

void trigger_init(void)
{
    s_q = xQueueCreate(8, sizeof(uint16_t));
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
    const uint16_t item = (uint16_t)src;
    xQueueSend(s_q, &item, 0);
}

void trigger_post_tone(uint8_t id)
{
    const uint16_t item = (uint16_t)TRIG_BLE_TONE | ((uint16_t)id << 8);
    xQueueSend(s_q, &item, 0);
}

bool trigger_wait(trigger_src_t *src, uint8_t *tone, TickType_t timeout)
{
    uint16_t item;
    if (xQueueReceive(s_q, &item, timeout) != pdTRUE) return false;
    *src = (trigger_src_t)(item & 0xff);
    *tone = (uint8_t)(item >> 8);
    return true;
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
    default: return "?";
    }
}
