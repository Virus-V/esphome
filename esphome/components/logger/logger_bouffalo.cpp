#include "logger.h"

#ifdef USE_BOUFFALO

#include <Arduino.h>

namespace esphome::logger {

ESPHOME_LOG_TAG(TAG, "logger");

void Logger::pre_setup() {
  if (this->baud_rate_ > 0) {
    switch (this->uart_) {
      case UART_SELECTION_UART0:
        this->hw_serial_ = &Serial;
        Serial.begin(this->baud_rate_);
        break;
      case UART_SELECTION_UART1:
        this->hw_serial_ = &Serial1;
        Serial1.begin(this->baud_rate_);
        break;
      default:
        this->hw_serial_ = &Serial;
        Serial.begin(this->baud_rate_);
        break;
    }
  }

  global_logger = this;
  ESP_LOGI(TAG, "Log initialized");
}

const LogString *Logger::get_uart_selection_() {
  switch (this->uart_) {
    case UART_SELECTION_UART0:
      return LOG_STR("UART0");
    case UART_SELECTION_UART1:
    default:
      return LOG_STR("UART1");
  }
}

}  // namespace esphome::logger

#endif  // USE_BOUFFALO
