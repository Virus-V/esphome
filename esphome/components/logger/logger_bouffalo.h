#pragma once

#ifdef USE_BOUFFALO

#include "esphome/core/helpers.h"

namespace esphome::logger {

/// Write a fully formatted log line to the configured hardware UART.
inline void HOT Logger::write_msg_(const char *message, uint16_t length) { this->hw_serial_->write(message, length); }

}  // namespace esphome::logger

#endif  // USE_BOUFFALO
