#include "ble.h"
#include "config.h"
#include "trigger.h"

#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gap_ble_api.h"
#include "esp_gatts_api.h"
#include "esp_gatt_common_api.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "ble";

/* 2139d58x-b04a-4808-8e1f-f08bb13d8de6, little-endian as Bluedroid wants. */
static const uint8_t UUID_SERVICE[16] = {0xe6, 0x8d, 0x3d, 0xb1, 0x8b, 0xf0, 0x1f, 0x8e,
                                         0x08, 0x48, 0x4a, 0xb0, 0x81, 0xd5, 0x39, 0x21};
static const uint8_t UUID_TRIGGER[16] = {0xe6, 0x8d, 0x3d, 0xb1, 0x8b, 0xf0, 0x1f, 0x8e,
                                         0x08, 0x48, 0x4a, 0xb0, 0x82, 0xd5, 0x39, 0x21};
static const uint8_t UUID_STATUS[16]  = {0xe6, 0x8d, 0x3d, 0xb1, 0x8b, 0xf0, 0x1f, 0x8e,
                                         0x08, 0x48, 0x4a, 0xb0, 0x83, 0xd5, 0x39, 0x21};

enum { IDX_SVC, IDX_TRIG_CHAR, IDX_TRIG_VAL, IDX_STAT_CHAR, IDX_STAT_VAL, IDX_STAT_CCC, IDX_NB };

static const uint16_t uuid_primary = ESP_GATT_UUID_PRI_SERVICE;
static const uint16_t uuid_char_decl = ESP_GATT_UUID_CHAR_DECLARE;
static const uint16_t uuid_ccc = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;
static const uint8_t prop_write = ESP_GATT_CHAR_PROP_BIT_WRITE;
static const uint8_t prop_read_notify = ESP_GATT_CHAR_PROP_BIT_READ | ESP_GATT_CHAR_PROP_BIT_NOTIFY;
static uint8_t trig_val[4];
static uint8_t stat_val = BLE_STATUS_IDLE;
static uint8_t ccc_val[2];

#define ENC_R  ESP_GATT_PERM_READ_ENCRYPTED
#define ENC_W  ESP_GATT_PERM_WRITE_ENCRYPTED

static const esp_gatts_attr_db_t s_db[IDX_NB] = {
    [IDX_SVC] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16, (uint8_t *)&uuid_primary, ESP_GATT_PERM_READ,
                  sizeof(UUID_SERVICE), sizeof(UUID_SERVICE), (uint8_t *)UUID_SERVICE}},
    [IDX_TRIG_CHAR] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16, (uint8_t *)&uuid_char_decl, ESP_GATT_PERM_READ,
                        1, 1, (uint8_t *)&prop_write}},
    [IDX_TRIG_VAL] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_128, (uint8_t *)UUID_TRIGGER, ENC_W,
                       sizeof(trig_val), 0, trig_val}},
    [IDX_STAT_CHAR] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16, (uint8_t *)&uuid_char_decl, ESP_GATT_PERM_READ,
                        1, 1, (uint8_t *)&prop_read_notify}},
    [IDX_STAT_VAL] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_128, (uint8_t *)UUID_STATUS, ENC_R,
                       1, 1, &stat_val}},
    [IDX_STAT_CCC] = {{ESP_GATT_AUTO_RSP}, {ESP_UUID_LEN_16, (uint8_t *)&uuid_ccc, ENC_R | ENC_W,
                       sizeof(ccc_val), sizeof(ccc_val), ccc_val}},
};

static uint16_t s_handles[IDX_NB];
static esp_gatt_if_t s_gatts_if = ESP_GATT_IF_NONE;
/* Up to BLE_MAX_LINKS centrals at once (phone app open + the laptop's mail watcher + one more). The controller is built
 * for 3 (CONFIG_BTDM_CTRL_BLE_MAX_CONN). Advertising restarts after each connect while a slot is free. */
#define BLE_MAX_LINKS 3
static struct { bool used; uint16_t conn_id; bool notify; } s_links[BLE_MAX_LINKS];

static int link_find(uint16_t conn_id)
{
    for (int i = 0; i < BLE_MAX_LINKS; i++) if (s_links[i].used && s_links[i].conn_id == conn_id) return i;
    return -1;
}

static int link_count(void)
{
    int n = 0;
    for (int i = 0; i < BLE_MAX_LINKS; i++) n += s_links[i].used;
    return n;
}
static int64_t s_pair_until_us;

/* Advertising: flags + complete list of 128-bit service UUIDs; name in the scan response. */
static uint8_t s_adv[3 + 18] = {0x02, ESP_BLE_AD_TYPE_FLAG, ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_BREDR_NOT_SPT,
                                0x11, ESP_BLE_AD_TYPE_128SRV_CMPL};
static uint8_t s_scan_rsp[2 + sizeof(BLE_DEVICE_NAME) - 1] = {sizeof(BLE_DEVICE_NAME), ESP_BLE_AD_TYPE_NAME_CMPL};

static esp_ble_adv_params_t s_adv_params = {
    .adv_int_min = 0x100,   /* 160 ms */
    .adv_int_max = 0x140,   /* 200 ms */
    .adv_type = ADV_TYPE_IND,
    .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
    .channel_map = ADV_CHNL_ALL,
    .adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
};

bool ble_pairing_is_open(void)
{
    return esp_timer_get_time() < s_pair_until_us;
}

void ble_pairing_open(int seconds)
{
    s_pair_until_us = esp_timer_get_time() + (int64_t)seconds * 1000000;
    ESP_LOGW(TAG, "pairing window open for %d s", seconds);
}

void ble_pairing_close(void)
{
    if (s_pair_until_us) ESP_LOGI(TAG, "pairing window closed");
    s_pair_until_us = 0;
}

static void log_bonds(void)
{
    int n = esp_ble_get_bond_device_num();
    ESP_LOGI(TAG, "bonded devices: %d", n);
    if (n <= 0) return;
    esp_ble_bond_dev_t *list = calloc(n, sizeof(*list));
    if (!list) return;
    esp_ble_get_bond_device_list(&n, list);
    for (int i = 0; i < n; i++) ESP_LOGI(TAG, "  " ESP_BD_ADDR_STR, ESP_BD_ADDR_HEX(list[i].bd_addr));
    free(list);
}

void ble_forget_all(void)
{
    int n = esp_ble_get_bond_device_num();
    if (n <= 0) return;
    esp_ble_bond_dev_t *list = calloc(n, sizeof(*list));
    if (!list) return;
    esp_ble_get_bond_device_list(&n, list);
    for (int i = 0; i < n; i++) esp_ble_remove_bond_device(list[i].bd_addr);
    free(list);
    ESP_LOGW(TAG, "removed %d bonded device(s)", n);
}

void ble_set_status(ble_status_t s)
{
    stat_val = (uint8_t)s;
    if (!s_handles[IDX_STAT_VAL]) return;
    esp_ble_gatts_set_attr_value(s_handles[IDX_STAT_VAL], 1, &stat_val);
    for (int i = 0; i < BLE_MAX_LINKS; i++) {
        if (s_links[i].used && s_links[i].notify)
            esp_ble_gatts_send_indicate(s_gatts_if, s_links[i].conn_id, s_handles[IDX_STAT_VAL], 1, &stat_val, false);
    }
}

static void gap_cb(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *p)
{
    switch (event) {
    case ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT:
        esp_ble_gap_config_scan_rsp_data_raw(s_scan_rsp, sizeof(s_scan_rsp));
        break;
    case ESP_GAP_BLE_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT:
        esp_ble_gap_start_advertising(&s_adv_params);
        break;
    case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
        if (p->adv_start_cmpl.status != ESP_BT_STATUS_SUCCESS)
            ESP_LOGE(TAG, "advertising failed: %d", p->adv_start_cmpl.status);
        else
            ESP_LOGI(TAG, "advertising as \"%s\"", BLE_DEVICE_NAME);
        break;
    case ESP_GAP_BLE_SEC_REQ_EVT: {
        /* A peer wants to pair. Accept only inside the pairing window. */
        bool ok = ble_pairing_is_open();
        ESP_LOGW(TAG, "pairing request from " ESP_BD_ADDR_STR ": %s",
                 ESP_BD_ADDR_HEX(p->ble_security.ble_req.bd_addr), ok ? "accepted" : "REJECTED (window closed)");
        esp_ble_gap_security_rsp(p->ble_security.ble_req.bd_addr, ok);
        break;
    }
    case ESP_GAP_BLE_NC_REQ_EVT:
        /* No IO on our side, so this should not happen; refuse rather than auto-confirm. */
        esp_ble_confirm_reply(p->ble_security.ble_req.bd_addr, ble_pairing_is_open());
        break;
    case ESP_GAP_BLE_AUTH_CMPL_EVT:
        if (p->ble_security.auth_cmpl.success) {
            ESP_LOGI(TAG, "link encrypted with " ESP_BD_ADDR_STR,
                     ESP_BD_ADDR_HEX(p->ble_security.auth_cmpl.bd_addr));
            log_bonds();
        } else {
            ESP_LOGW(TAG, "pairing/encryption failed with " ESP_BD_ADDR_STR ", reason 0x%x",
                     ESP_BD_ADDR_HEX(p->ble_security.auth_cmpl.bd_addr), p->ble_security.auth_cmpl.fail_reason);
        }
        break;
    default:
        break;
    }
}

static void gatts_cb(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if, esp_ble_gatts_cb_param_t *p)
{
    switch (event) {
    case ESP_GATTS_REG_EVT:
        if (p->reg.status != ESP_GATT_OK) {
            ESP_LOGE(TAG, "GATT app register failed: %d", p->reg.status);
            return;
        }
        s_gatts_if = gatts_if;
        esp_ble_gap_set_device_name(BLE_DEVICE_NAME);
        esp_ble_gap_config_adv_data_raw(s_adv, sizeof(s_adv));
        esp_ble_gatts_create_attr_tab(s_db, gatts_if, IDX_NB, 0);
        break;
    case ESP_GATTS_CREAT_ATTR_TAB_EVT:
        if (p->add_attr_tab.status != ESP_GATT_OK || p->add_attr_tab.num_handle != IDX_NB) {
            ESP_LOGE(TAG, "attribute table failed: status %d, %d handles", p->add_attr_tab.status,
                     p->add_attr_tab.num_handle);
            return;
        }
        memcpy(s_handles, p->add_attr_tab.handles, sizeof(s_handles));
        esp_ble_gatts_start_service(s_handles[IDX_SVC]);
        break;
    case ESP_GATTS_CONNECT_EVT:
        for (int i = 0; i < BLE_MAX_LINKS; i++) {
            if (!s_links[i].used) {
                s_links[i].used = true;
                s_links[i].conn_id = p->connect.conn_id;
                s_links[i].notify = false;
                break;
            }
        }
        ESP_LOGI(TAG, "connected: " ESP_BD_ADDR_STR " (%d of %d links)", ESP_BD_ADDR_HEX(p->connect.remote_bda),
                 link_count(), BLE_MAX_LINKS);
        if (link_count() < BLE_MAX_LINKS) esp_ble_gap_start_advertising(&s_adv_params);   /* stay reachable */
        break;
    case ESP_GATTS_DISCONNECT_EVT:
        {
            int i = link_find(p->disconnect.conn_id);
            if (i >= 0) s_links[i].used = false;
        }
        ESP_LOGI(TAG, "disconnected: " ESP_BD_ADDR_STR ", reason 0x%x (%d links left)",
                 ESP_BD_ADDR_HEX(p->disconnect.remote_bda), p->disconnect.reason, link_count());
        esp_ble_gap_start_advertising(&s_adv_params);
        break;
    case ESP_GATTS_WRITE_EVT:
        /* The stack has already rejected writes on an unencrypted link (ENC_W). */
        if (p->write.handle == s_handles[IDX_STAT_CCC] && p->write.len == 2) {
            int i = link_find(p->write.conn_id);
            if (i >= 0) s_links[i].notify = p->write.value[0] & 0x01;
            ESP_LOGI(TAG, "status notifications %s (link %d)", (p->write.value[0] & 0x01) ? "on" : "off", i);
        } else if (p->write.handle == s_handles[IDX_TRIG_VAL]) {
            uint8_t v = p->write.len >= 1 ? p->write.value[0] : 0;
            if (v == BLE_CMD_RING) {
                ESP_LOGI(TAG, "trigger write: ring");
                trigger_post(TRIG_BLE);
            } else if (v == BLE_CMD_RING_NET) {
                ESP_LOGI(TAG, "trigger write: ring (internet call)");
                trigger_post(TRIG_BLE_NET);
            } else if (v == BLE_CMD_IDENTIFY) {
                ESP_LOGI(TAG, "trigger write: identify (blink LED)");
                trigger_post(TRIG_BLE_IDENTIFY);
            } else if (v >= BLE_CMD_TONE_BASE && v <= BLE_CMD_TONE_MAX) {
                ESP_LOGI(TAG, "trigger write: ringtone %d", v - BLE_CMD_TONE_BASE);
                trigger_post_tone(v - BLE_CMD_TONE_BASE);
            } else {
                ESP_LOGW(TAG, "trigger write 0x%02x ignored", v);
            }
        }
        break;
    default:
        break;
    }
}

esp_err_t ble_init(void)
{
    memcpy(&s_adv[5], UUID_SERVICE, 16);
    memcpy(&s_scan_rsp[2], BLE_DEVICE_NAME, sizeof(BLE_DEVICE_NAME) - 1);

    ESP_ERROR_CHECK(esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT));   /* BLE only for now */
    esp_bt_controller_config_t cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_bt_controller_init(&cfg));
    ESP_LOGD(TAG, "init: esp_bt_controller_init done");
    ESP_ERROR_CHECK(esp_bt_controller_enable(ESP_BT_MODE_BLE));
    ESP_LOGD(TAG, "init: esp_bt_controller_enable done");
    ESP_ERROR_CHECK(esp_bluedroid_init());
    ESP_LOGD(TAG, "init: esp_bluedroid_init done");
    ESP_ERROR_CHECK(esp_bluedroid_enable());
    ESP_LOGD(TAG, "init: esp_bluedroid_enable done");
    ESP_ERROR_CHECK(esp_ble_gap_register_callback(gap_cb));
    ESP_ERROR_CHECK(esp_ble_gatts_register_callback(gatts_cb));

    /* Just Works + LE Secure Connections + bonding. No IO on the box, so no MITM
     * protection: the pairing window is what keeps strangers out. */
    esp_ble_auth_req_t auth = ESP_LE_AUTH_REQ_SC_BOND;
    esp_ble_io_cap_t iocap = ESP_IO_CAP_NONE;
    uint8_t key_size = 16;
    uint8_t init_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
    uint8_t rsp_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
    uint8_t oob = ESP_BLE_OOB_DISABLE;
    esp_ble_gap_set_security_param(ESP_BLE_SM_AUTHEN_REQ_MODE, &auth, sizeof(auth));
    esp_ble_gap_set_security_param(ESP_BLE_SM_IOCAP_MODE, &iocap, sizeof(iocap));
    esp_ble_gap_set_security_param(ESP_BLE_SM_MAX_KEY_SIZE, &key_size, sizeof(key_size));
    esp_ble_gap_set_security_param(ESP_BLE_SM_OOB_SUPPORT, &oob, sizeof(oob));
    esp_ble_gap_set_security_param(ESP_BLE_SM_SET_INIT_KEY, &init_key, sizeof(init_key));
    esp_ble_gap_set_security_param(ESP_BLE_SM_SET_RSP_KEY, &rsp_key, sizeof(rsp_key));

    ESP_ERROR_CHECK(esp_ble_gatts_app_register(0));
    ESP_LOGD(TAG, "init: esp_ble_gatts_app_register done");
    esp_ble_gatt_set_local_mtu(64);
    log_bonds();
    return ESP_OK;
}
