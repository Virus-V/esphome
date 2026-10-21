#include "esphome/core/main_task.h"

#if defined(USE_ESP32) || defined(USE_LIBRETINY) || defined(USE_BOUFFALO)
TaskHandle_t esphome_main_task_handle = NULL;
#endif
