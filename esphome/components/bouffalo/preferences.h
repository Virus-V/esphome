#pragma once

#ifdef USE_BOUFFALO

#include <vector>

#include "esphome/core/preference_backend.h"

namespace esphome::bouffalo {

class BouffaloPreferences final : public PreferencesMixin<BouffaloPreferences> {
 public:
  using PreferencesMixin<BouffaloPreferences>::make_preference;

  ESPPreferenceObject make_preference(size_t length, uint32_t key, bool in_flash);
  ESPPreferenceObject make_preference(size_t length, uint32_t key) { return this->make_preference(length, key, true); }
  bool load_from_key(uint32_t key, uint8_t *data, size_t len);
  bool sync();
  bool reset();

 protected:
  std::vector<BouffaloPreferenceBackend *> entries_;
  bool reset_{false};
};

void setup_preferences();

}  // namespace esphome::bouffalo

DECLARE_PREFERENCE_ALIASES(esphome::bouffalo::BouffaloPreferences)

#endif  // USE_BOUFFALO
