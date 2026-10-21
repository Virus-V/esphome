#include "esphome/core/hal.h"

#ifdef USE_BOUFFALO

#include "bflb_efuse.h"
#include "bflb_irq.h"
#include "bflb_sec_trng.h"
#include "preferences.h"

extern "C" {
#include "bl616cl_sys.h"
}

namespace esphome::bouffalo {}

namespace esphome {

void arch_init() {
  esphome_main_task_handle = xTaskGetCurrentTaskHandle();
  bouffalo::setup_preferences();
}

void __attribute__((noreturn)) arch_restart() {
  bl_sys_reset_system();
  while (true) {
  }
}

bool random_bytes(uint8_t *data, size_t len) { return len == 0 || bflb_trng_readlen(data, len) == 0; }

void get_mac_address_raw(uint8_t *mac) {
  if (bflb_efuse_read_mac_address(mac, 1) != 0) {
    abort();
  }
}

InterruptLock::InterruptLock() { this->state_ = bflb_irq_save(); }
InterruptLock::~InterruptLock() { bflb_irq_restore(this->state_); }

}  // namespace esphome

#endif  // USE_BOUFFALO
