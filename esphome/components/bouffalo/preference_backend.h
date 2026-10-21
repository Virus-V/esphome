#pragma once

#ifdef USE_BOUFFALO

#include <cstddef>
#include <cstdint>
#include <vector>

namespace esphome::bouffalo {

class BouffaloPreferences;

BouffaloPreferences *get_preferences();

class BouffaloPreferenceBackend {
 public:
  BouffaloPreferenceBackend(uint32_t key, size_t length) : key(key), data(length) {}

  bool save(const uint8_t *src, size_t len);
  bool load(uint8_t *dest, size_t len);

  uint32_t key;
  std::vector<uint8_t> data;
  bool loaded{false};
  bool dirty{false};
};

}  // namespace esphome::bouffalo

namespace esphome {
using PreferenceBackend = bouffalo::BouffaloPreferenceBackend;
}  // namespace esphome

#endif  // USE_BOUFFALO
