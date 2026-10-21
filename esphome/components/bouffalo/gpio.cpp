#include "esphome/core/hal.h"

#ifdef USE_BOUFFALO

#include "gpio.h"

#include <cstdio>
#include <iterator>

#include "bflb_gpio.h"

namespace esphome::bouffalo {

struct GPIOCallback {
  void (*function)(void *){nullptr};
  void *argument{nullptr};
};

// BL616CL exposes GPIO0 through GPIO36.
static GPIOCallback s_callbacks[37];

static bflb_device_s *gpio_device() { return bflb_device_get_by_name("gpio"); }

static uint32_t pull_config(gpio::Flags flags) {
  const auto raw = static_cast<uint8_t>(flags);
  if (raw & gpio::FLAG_PULLUP)
    return GPIO_PULLUP;
  if (raw & gpio::FLAG_PULLDOWN)
    return GPIO_PULLDOWN;
  return GPIO_FLOAT;
}

static void IRAM_ATTR gpio_interrupt(uint8_t pin) {
  bflb_gpio_int_clear(gpio_device(), pin);
  if (pin < std::size(s_callbacks) && s_callbacks[pin].function != nullptr) {
    s_callbacks[pin].function(s_callbacks[pin].argument);
  }
}

void BouffaloGPIOPin::pin_mode(gpio::Flags flags) {
  this->flags_ = flags;
  const auto raw = static_cast<uint8_t>(flags);
  const bool open_drain = raw & gpio::FLAG_OPEN_DRAIN;

  uint32_t config = GPIO_SMT_EN | GPIO_DRV_1 | pull_config(flags);
  if ((raw & gpio::FLAG_INPUT) || open_drain) {
    config |= GPIO_INPUT;
  }
  if ((raw & gpio::FLAG_OUTPUT) && !open_drain) {
    config |= GPIO_OUTPUT;
  }
  bflb_gpio_init(gpio_device(), this->pin_, config);
}

bool BouffaloGPIOPin::digital_read() { return (bflb_gpio_read(gpio_device(), this->pin_) != 0) != this->inverted_; }

void BouffaloGPIOPin::digital_write(bool value) {
  value = value != this->inverted_;
  if (static_cast<uint8_t>(this->flags_) & gpio::FLAG_OPEN_DRAIN) {
    uint32_t config = GPIO_SMT_EN | GPIO_DRV_1 | pull_config(this->flags_);
    if (value) {
      bflb_gpio_reset(gpio_device(), this->pin_);
      bflb_gpio_init(gpio_device(), this->pin_, config | GPIO_INPUT);
    } else {
      bflb_gpio_reset(gpio_device(), this->pin_);
      bflb_gpio_init(gpio_device(), this->pin_, config | GPIO_OUTPUT);
    }
  } else if (value) {
    bflb_gpio_set(gpio_device(), this->pin_);
  } else {
    bflb_gpio_reset(gpio_device(), this->pin_);
  }
}

size_t BouffaloGPIOPin::dump_summary(char *buffer, size_t len) const {
  return snprintf(buffer, len, "GPIO%u", this->pin_);
}

void BouffaloGPIOPin::detach_interrupt() const {
  bflb_gpio_int_mask(gpio_device(), this->pin_, true);
  s_callbacks[this->pin_] = {};
}

void BouffaloGPIOPin::attach_interrupt_(void (*func)(void *), void *arg, gpio::InterruptType type) const {
  uint8_t trigger_mode = GPIO_INT_TRIG_MODE_SYNC_FALLING_RISING_EDGE;
  switch (type) {
    case gpio::INTERRUPT_RISING_EDGE:
      trigger_mode = this->inverted_ ? GPIO_INT_TRIG_MODE_ASYNC_FALLING_EDGE : GPIO_INT_TRIG_MODE_ASYNC_RISING_EDGE;
      break;
    case gpio::INTERRUPT_FALLING_EDGE:
      trigger_mode = this->inverted_ ? GPIO_INT_TRIG_MODE_ASYNC_RISING_EDGE : GPIO_INT_TRIG_MODE_ASYNC_FALLING_EDGE;
      break;
    case gpio::INTERRUPT_ANY_EDGE:
      trigger_mode = GPIO_INT_TRIG_MODE_SYNC_FALLING_RISING_EDGE;
      break;
    case gpio::INTERRUPT_LOW_LEVEL:
      trigger_mode = this->inverted_ ? GPIO_INT_TRIG_MODE_ASYNC_HIGH_LEVEL : GPIO_INT_TRIG_MODE_ASYNC_LOW_LEVEL;
      break;
    case gpio::INTERRUPT_HIGH_LEVEL:
      trigger_mode = this->inverted_ ? GPIO_INT_TRIG_MODE_ASYNC_LOW_LEVEL : GPIO_INT_TRIG_MODE_ASYNC_HIGH_LEVEL;
      break;
  }

  bflb_gpio_int_mask(gpio_device(), this->pin_, true);
  s_callbacks[this->pin_] = {func, arg};
  bflb_gpio_int_init(gpio_device(), this->pin_, trigger_mode);
  bflb_gpio_irq_attach(this->pin_, gpio_interrupt);
  bflb_gpio_int_clear(gpio_device(), this->pin_);
  bflb_gpio_int_mask(gpio_device(), this->pin_, false);
}

}  // namespace esphome::bouffalo

namespace esphome {

bool IRAM_ATTR ISRInternalGPIOPin::digital_read() {
  return static_cast<bouffalo::BouffaloGPIOPin *>(this->arg_)->digital_read();
}

void IRAM_ATTR ISRInternalGPIOPin::digital_write(bool value) {
  static_cast<bouffalo::BouffaloGPIOPin *>(this->arg_)->digital_write(value);
}

void IRAM_ATTR ISRInternalGPIOPin::pin_mode(gpio::Flags flags) {
  static_cast<bouffalo::BouffaloGPIOPin *>(this->arg_)->pin_mode(flags);
}

void IRAM_ATTR ISRInternalGPIOPin::clear_interrupt() {
  static_cast<bouffalo::BouffaloGPIOPin *>(this->arg_)->detach_interrupt();
}

}  // namespace esphome

#endif  // USE_BOUFFALO
