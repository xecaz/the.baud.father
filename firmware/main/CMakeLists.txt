idf_component_register(
    SRCS "main.c" "modem.c" "audio.c" "trigger.c" "ble.c" "console.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES esp_driver_gpio esp_driver_uart esp_driver_dac esp_timer esp_hw_support bt nvs_flash esp_partition
)
