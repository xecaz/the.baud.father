#include "audio.h"
#include "config.h"

#include <math.h>
#include <string.h>
#include "clk_ctrl_os.h"
#include "driver/dac_continuous.h"
#include "esp_log.h"
#include "esp_partition.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static const char *TAG = "audio";

/* ---- Sound bank (layout written by tools/mksounds.py; keep both in sync) ----
 * header (16 bytes): "SNDB", u16 version = 1, u16 count, u32 rate, u32 data_end
 * count entries (32 bytes): char name[24] (NUL padded), u32 offset, u32 length   (from partition start)
 * then the clips: u8 unsigned PCM, 128 = silence. Little endian. */
#define BANK_MAGIC      "SNDB"
#define BANK_VERSION    1
#define BANK_MAX_CLIPS  256
#define BANK_SUBTYPE    0x40          /* partitions.csv: sounds, data, 0x40 */

typedef struct __attribute__((packed)) {
    char magic[4];
    uint16_t version, count;
    uint32_t rate, data_end;
} bank_header_t;

typedef struct __attribute__((packed)) {
    char name[24];
    uint32_t offset, length;
} bank_entry_t;

static const uint8_t *s_bank;          /* mmapped partition, NULL if no bank */
static const bank_entry_t *s_entries;
static int s_count;

/* ---- Player ---- */
#define CHUNK           512           /* samples per write: 64 ms at 8 kHz */
#define DMA_DESCS       4
#define DMA_BUF_BYTES   (CHUNK * 2)   /* the ESP32 DMA DAC takes 16-bit words; the driver expands */
#define DRAIN_MS        (DMA_DESCS * CHUNK * 1000 / AUDIO_RATE_HZ + 40)
#define RAMP_OPEN_MS    60            /* 0 V -> mid-scale; slow so the coupling cap does not thump */
#define RAMP_SWITCH_MS  8

typedef enum { CMD_PLAY, CMD_SEQ, CMD_TONE, CMD_STOP } cmd_kind_t;
typedef struct { cmd_kind_t kind; int idx, hz, level, gap_ms; uint8_t n, seq[AUDIO_SEQ_MAX]; } cmd_t;

static QueueHandle_t s_q;
static EventGroupHandle_t s_ev;
#define EV_IDLE BIT0

static dac_continuous_handle_t s_dac;
static uint8_t s_last;                /* last value written: ramps start from here */
static uint8_t s_buf[CHUNK];
/* Samples collected for the next full CHUNK (see out()). */
static uint8_t s_acc[CHUNK], s_swapped[CHUNK];
static size_t s_acc_n;
static int8_t s_sine[256];

static void dac_open(void)
{
    const dac_continuous_config_t cfg = {
        .chan_mask = DAC_CHANNEL_MASK_CH0,     /* GPIO25 */
        .desc_num = DMA_DESCS,
        .buf_size = DMA_BUF_BYTES,
        .freq_hz = AUDIO_RATE_HZ,
        .offset = 0,
        .clk_src = DAC_DIGI_CLK_SRC_APLL,      /* the default PLL_D2 clock cannot go below 19.6 kHz */
        .chan_mode = DAC_CHANNEL_MODE_SIMUL,
    };
    ESP_ERROR_CHECK(dac_continuous_new_channels(&cfg, &s_dac));
    ESP_ERROR_CHECK(dac_continuous_enable(s_dac));
    s_last = 0;
    s_acc_n = 0;
}

static void flush(void);

static void dac_close(void)
{
    flush();
    vTaskDelay(pdMS_TO_TICKS(DRAIN_MS));       /* let the queued DMA buffers play out */
    ESP_ERROR_CHECK(dac_continuous_disable(s_dac));   /* powers the DAC down: pin floats */
    ESP_ERROR_CHECK(dac_continuous_del_channels(s_dac));
    s_dac = NULL;
}

/* The ESP32 DMA DAC plays each pair of samples swapped (2,1,4,3...): its I2S "mono" still sends
 * left/right words in the wrong order. Heard 2026-11-09 as a 3575 Hz ghost on the 425 Hz tone (every
 * frequency mirrored around fs/2). Pre-swap the pairs.
 *
 * The driver only ever gets whole CHUNKs: out() collects the samples and flush() pads the last one. Short writes
 * each take descriptors of their own (the driver splits every write in two), and several in a row (clip tail, ramp,
 * word gap, ramp) stalled dac_continuous_write() for good in the middle of a sentence (2026-11-21, IDF 5.5.1). */

static void write_chunk(void)
{
    for (size_t i = 0; i < CHUNK; i += 2) {
        s_swapped[i] = s_acc[i + 1];
        s_swapped[i + 1] = s_acc[i];
    }
    dac_continuous_write(s_dac, s_swapped, CHUNK, NULL, -1);
    s_acc_n = 0;
}

static void out(const uint8_t *buf, size_t n)
{
    if (!n) return;
    s_last = buf[n - 1];
    while (n) {
        size_t k = CHUNK - s_acc_n < n ? CHUNK - s_acc_n : n;
        memcpy(s_acc + s_acc_n, buf, k);
        s_acc_n += k;
        buf += k;
        n -= k;
        if (s_acc_n == CHUNK) write_chunk();
    }
}

/* Send what is still collected, padded with the last value (before the DAC is closed). */
static void flush(void)
{
    if (!s_acc_n) return;
    memset(s_acc + s_acc_n, s_last, CHUNK - s_acc_n);
    write_chunk();
}

static void ramp(uint8_t to, int ms)
{
    int n = ms * AUDIO_RATE_HZ / 1000;
    if (n < 1) n = 1;
    const int from = s_last;
    for (int done = 0; done < n;) {
        int k = n - done > CHUNK ? CHUNK : n - done;
        for (int i = 0; i < k; i++) s_buf[i] = from + (to - from) * (done + i + 1) / n;
        out(s_buf, k);
        done += k;
    }
}

static volatile int s_clip_level = AUDIO_LEVEL;   /* 256 = full scale */
void audio_set_level(int level) { s_clip_level = level < 0 ? 0 : level > 256 ? 256 : level; }

static inline uint8_t scale(uint8_t s)
{
    return 128 + (((int)s - 128) * s_clip_level >> 8);
}

/* One clip to its end. Returns true with *next filled if interrupted by a command. */
static bool play_clip(int idx, cmd_t *next)
{
    const bank_entry_t *e = &s_entries[idx];
    const uint8_t *p = s_bank + e->offset;
    ESP_LOGI(TAG, "play \"%.24s\" (%lu ms)", e->name, (unsigned long)audio_len_ms(idx));
    if (e->length) ramp(scale(p[0]), RAMP_SWITCH_MS);
    for (uint32_t pos = 0; pos < e->length;) {
        if (xQueueReceive(s_q, next, 0) == pdTRUE) return true;
        uint32_t k = e->length - pos > CHUNK ? CHUNK : e->length - pos;
        for (uint32_t i = 0; i < k; i++) s_buf[i] = scale(p[pos + i]);
        out(s_buf, k);
        pos += k;
    }
    return false;
}

/* Mid-scale for ms (between the clips of a sequence). */
static bool silence(int ms, cmd_t *next)
{
    ramp(128, RAMP_SWITCH_MS);
    for (int left = ms * AUDIO_RATE_HZ / 1000; left > 0;) {
        if (xQueueReceive(s_q, next, 0) == pdTRUE) return true;
        int k = left > CHUNK ? CHUNK : left;
        memset(s_buf, 128, (size_t)k);
        out(s_buf, (size_t)k);
        left -= k;
    }
    return false;
}

/* Plays one source until it ends or another command arrives.
 * Returns true with *next filled if interrupted by a command. */
static bool run_source(const cmd_t *c, cmd_t *next)
{
    if (c->kind == CMD_PLAY) return play_clip(c->idx, next);
    if (c->kind == CMD_SEQ) {
        for (int i = 0; i < c->n; i++) {
            if (i && silence(c->gap_ms, next)) return true;
            if (play_clip(c->seq[i], next)) return true;
        }
        return false;
    }
    /* CMD_TONE: phase accumulator over a 256-entry sine table. */
    const uint32_t inc = (uint32_t)((double)c->hz * 4294967296.0 / AUDIO_RATE_HZ);
    const int level = c->level < 1 ? 1 : c->level > 127 ? 127 : c->level;
    uint32_t phase = 0;
    ESP_LOGI(TAG, "tone %d Hz, level %d", c->hz, level);
    for (;;) {
        if (xQueueReceive(s_q, next, 0) == pdTRUE) return true;
        for (int i = 0; i < CHUNK; i++) {
            s_buf[i] = 128 + s_sine[phase >> 24] * level / 127;
            phase += inc;
        }
        out(s_buf, CHUNK);
    }
}

static void audio_task(void *arg)
{
    cmd_t c, next;
    for (;;) {
        if (uxQueueMessagesWaiting(s_q) == 0) xEventGroupSetBits(s_ev, EV_IDLE);
        xQueueReceive(s_q, &c, portMAX_DELAY);
        if (c.kind == CMD_STOP) continue;

        dac_open();
        ramp(128, RAMP_OPEN_MS);
        for (;;) {
            bool interrupted = run_source(&c, &next);
            ramp(128, RAMP_SWITCH_MS);
            if (!interrupted) {
                /* Clip ended: chain straight into a command that is already waiting. */
                if (xQueueReceive(s_q, &next, 0) != pdTRUE) break;
            }
            if (next.kind == CMD_STOP) break;
            c = next;
        }
        ramp(0, RAMP_OPEN_MS);
        dac_close();
        ESP_LOGD(TAG, "idle (DAC off)");
    }
}

static void send(cmd_t c)
{
    xEventGroupClearBits(s_ev, EV_IDLE);
    xQueueSend(s_q, &c, portMAX_DELAY);
}

/* ---- Bank loading ---- */

static void load_bank(void)
{
    const esp_partition_t *part = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, BANK_SUBTYPE, "sounds");
    if (!part) {
        ESP_LOGW(TAG, "no \"sounds\" partition (old partition table?): tones only");
        return;
    }
    bank_header_t h;
    if (esp_partition_read(part, 0, &h, sizeof h) != ESP_OK || memcmp(h.magic, BANK_MAGIC, 4) != 0) {
        ESP_LOGW(TAG, "no sound bank flashed (run tools/mksounds.py, then idf.py flash): tones only");
        return;
    }
    if (h.version != BANK_VERSION || h.count > BANK_MAX_CLIPS || h.data_end > part->size
        || h.data_end < sizeof h + h.count * sizeof(bank_entry_t)) {
        ESP_LOGE(TAG, "sound bank header invalid (version %u, %u clips, %lu bytes)",
                 h.version, h.count, (unsigned long)h.data_end);
        return;
    }
    if (h.rate != AUDIO_RATE_HZ) {
        ESP_LOGW(TAG, "sound bank is %lu Hz, player runs at %d Hz: clips will play at the wrong speed",
                 (unsigned long)h.rate, AUDIO_RATE_HZ);
    }
    const void *ptr;
    esp_partition_mmap_handle_t mh;
    if (esp_partition_mmap(part, 0, h.data_end, ESP_PARTITION_MMAP_DATA, &ptr, &mh) != ESP_OK) {
        ESP_LOGE(TAG, "mmap of the sound bank failed");
        return;
    }
    const uint8_t *base = ptr;
    const bank_entry_t *e = (const bank_entry_t *)(base + sizeof h);
    for (int i = 0; i < h.count; i++) {
        if (e[i].offset > h.data_end || e[i].length > h.data_end - e[i].offset) {
            ESP_LOGE(TAG, "sound bank entry %d out of range", i);
            esp_partition_munmap(mh);
            return;
        }
    }
    s_bank = base;
    s_entries = e;
    s_count = h.count;
    ESP_LOGI(TAG, "sound bank: %d clips, %lu KB", s_count, (unsigned long)h.data_end / 1024);
    for (int i = 0; i < s_count; i++) {
        ESP_LOGI(TAG, "  %d: %.24s (%lu ms)", i, e[i].name, (unsigned long)audio_len_ms(i));
    }
}

/* ---- Public API ---- */

esp_err_t audio_init(void)
{
    /* Hold one reference to the 8 MHz RC clock for good. The old cosine-generator dial tone
     * switched it off while measuring it, which hung esp_bluedroid_enable() (bisected 2026-11-07,
     * ESP-IDF 5.5.1). The DMA path does not touch it, but the reference costs nothing and keeps
     * BT safe if the cosine driver ever comes back. */
    if (!periph_rtc_dig_clk8m_enable()) return ESP_FAIL;

    for (int i = 0; i < 256; i++) s_sine[i] = (int8_t)lroundf(127.0f * sinf(2.0f * (float)M_PI * i / 256.0f));
    load_bank();

    s_q = xQueueCreate(4, sizeof(cmd_t));
    s_ev = xEventGroupCreate();
    if (!s_q || !s_ev) return ESP_ERR_NO_MEM;
    xEventGroupSetBits(s_ev, EV_IDLE);
    /* Core 1: Bluetooth runs on core 0. Above the main loop's priority so the DMA never starves. */
    if (xTaskCreatePinnedToCore(audio_task, "audio", 3072, NULL, 6, NULL, 1) != pdPASS) return ESP_ERR_NO_MEM;
    return ESP_OK;
}

int audio_count(void) { return s_count; }

const char *audio_name(int idx)
{
    return idx >= 0 && idx < s_count ? s_entries[idx].name : NULL;
}

int audio_find(const char *name)
{
    for (int i = 0; i < s_count; i++) {
        if (strncmp(s_entries[i].name, name, sizeof s_entries[i].name) == 0) return i;
    }
    return -1;
}

int audio_find_prefix(const char *prefix)
{
    const size_t n = strlen(prefix);
    if (n > sizeof s_entries[0].name) return -1;
    for (int i = 0; i < s_count; i++) {
        if (strncmp(s_entries[i].name, prefix, n) == 0) return i;
    }
    return -1;
}

uint32_t audio_len_ms(int idx)
{
    if (idx < 0 || idx >= s_count) return 0;
    return (uint32_t)((uint64_t)s_entries[idx].length * 1000 / AUDIO_RATE_HZ);
}

bool audio_play(int idx)
{
    if (idx < 0 || idx >= s_count) return false;
    send((cmd_t){ .kind = CMD_PLAY, .idx = idx });
    return true;
}

bool audio_play_seq(const int *idx, int n, int gap_ms)
{
    if (n < 1 || n > AUDIO_SEQ_MAX) return false;
    cmd_t c = { .kind = CMD_SEQ, .n = (uint8_t)n, .gap_ms = gap_ms < 0 ? 0 : gap_ms };
    for (int i = 0; i < n; i++) {
        if (idx[i] < 0 || idx[i] >= s_count) return false;
        c.seq[i] = (uint8_t)idx[i];      /* BANK_MAX_CLIPS is 256 */
    }
    send(c);
    return true;
}

bool audio_play_name(const char *name)
{
    int idx = audio_find(name);
    if (idx < 0) {
        ESP_LOGW(TAG, "no clip \"%s\" in the sound bank", name);
        return false;
    }
    return audio_play(idx);
}

void audio_tone(int hz, int level)
{
    send((cmd_t){ .kind = CMD_TONE, .hz = hz, .level = level });
}

void audio_stop(void)
{
    send((cmd_t){ .kind = CMD_STOP });
    xEventGroupWaitBits(s_ev, EV_IDLE, pdFALSE, pdTRUE, portMAX_DELAY);
}

bool audio_wait(int timeout_ms)
{
    TickType_t t = timeout_ms < 0 ? portMAX_DELAY : pdMS_TO_TICKS(timeout_ms);
    return xEventGroupWaitBits(s_ev, EV_IDLE, pdFALSE, pdTRUE, t) & EV_IDLE;
}

bool audio_busy(void)
{
    return !(xEventGroupGetBits(s_ev) & EV_IDLE);
}
