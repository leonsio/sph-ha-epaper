#pragma once

#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esphome/core/defines.h"
#include "driver/rtc_io.h"

// Persists across ESP32 deep-sleep resets without flash writes.
RTC_DATA_ATTR uint32_t e1003_rtc_boot_count = 0;
