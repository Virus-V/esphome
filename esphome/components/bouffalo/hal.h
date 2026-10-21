#pragma once

#ifdef USE_BOUFFALO

#include <cstdint>

#include <FreeRTOS.h>
#include <task.h>

#include "bflb_clock.h"
#include "bflb_mtimer.h"
#include "esphome/core/main_task.h"

// BL616CL code placed in `.tcm_code` remains executable while flash is busy.
#define IRAM_ATTR __attribute__((noinline, section(".tcm_code")))
#define PROGMEM

// Arduino core declarations used by the inline HAL wrappers below.
// NOLINTBEGIN(google-runtime-int,readability-identifier-naming,readability-redundant-declaration)
extern "C" void yield(void);
extern "C" void delay(unsigned long ms);
extern "C" void delayMicroseconds(unsigned int us);
// NOLINTEND(google-runtime-int,readability-identifier-naming,readability-redundant-declaration)

namespace esphome::bouffalo {}

namespace esphome {

__attribute__((always_inline)) inline bool in_isr_context() { return xPortIsInsideInterrupt() != 0; }

__attribute__((always_inline)) inline bool is_main_loop_thread() {
  return xTaskGetCurrentTaskHandle() == esphome_main_task_handle;
}

__attribute__((always_inline)) inline void yield() { ::yield(); }
__attribute__((always_inline)) inline void delay(uint32_t ms) { ::delay(ms); }
__attribute__((always_inline)) inline void delayMicroseconds(uint32_t us) { ::delayMicroseconds(us); }
__attribute__((always_inline)) inline uint32_t micros() { return static_cast<uint32_t>(bflb_mtimer_get_time_us()); }
__attribute__((always_inline)) inline uint32_t millis() { return static_cast<uint32_t>(bflb_mtimer_get_time_ms()); }
__attribute__((always_inline)) inline uint64_t millis_64() { return bflb_mtimer_get_time_ms(); }

__attribute__((always_inline)) inline uint32_t arch_get_cpu_cycle_count() {
  uint32_t cycle;
  __asm__ volatile("csrr %0, mcycle" : "=r"(cycle));
  return cycle;
}

__attribute__((always_inline)) inline uint32_t arch_get_cpu_freq_hz() {
  return bflb_clk_get_system_clock(BFLB_SYSTEM_CPU_CLK);
}

// BL616CL does not run a hardware watchdog in this Arduino profile.
__attribute__((always_inline)) inline void arch_feed_wdt() {}

void arch_init();

}  // namespace esphome

#endif  // USE_BOUFFALO
