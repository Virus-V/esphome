#pragma once

#ifdef USE_BOUFFALO

#include "esphome/core/gpio_pin.h"

namespace esphome::bouffalo {

class BouffaloGPIOPin final : public GPIOPin {
 public:
  void set_pin(uint8_t pin) { this->pin_ = pin; }
  void set_inverted(bool inverted) { this->inverted_ = inverted; }
  void set_flags(gpio::Flags flags) { this->flags_ = flags; }

  void setup() override { this->pin_mode(this->flags_); }
  void pin_mode(gpio::Flags flags) override;
  bool digital_read() override;
  void digital_write(bool value) override;
  gpio::Flags get_flags() const override { return this->flags_; }
  bool is_internal() override { return true; }
  uint8_t get_pin() const { return this->pin_; }
  bool is_inverted() const { return this->inverted_; }
  size_t dump_summary(char *buffer, size_t len) const override;
  ISRInternalGPIOPin to_isr() const { return ISRInternalGPIOPin(const_cast<BouffaloGPIOPin *>(this)); }
  void detach_interrupt() const;

  template<typename T> void attach_interrupt(void (*func)(T *), T *arg, gpio::InterruptType type) const {
    this->attach_interrupt_(reinterpret_cast<void (*)(void *)>(func), arg, type);
  }

 protected:
  void attach_interrupt_(void (*func)(void *), void *arg, gpio::InterruptType type) const;

  uint8_t pin_{0};
  bool inverted_{false};
  gpio::Flags flags_{gpio::FLAG_NONE};
};

}  // namespace esphome::bouffalo

#endif  // USE_BOUFFALO
