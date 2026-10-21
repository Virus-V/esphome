#include "esphome/core/defines.h"

#ifdef USE_BOUFFALO

#include "preferences.h"

#include <cstdio>
#include <cstring>

#include <Preferences.h>

namespace esphome {

ESPPreferences *global_preferences{nullptr};  // NOLINT(cppcoreguidelines-avoid-non-const-global-variables)

}  // namespace esphome

namespace esphome::bouffalo {

static ::Preferences s_storage;
static bool s_ready{false};

static bool open_storage() {
  if (!s_ready) {
    s_ready = s_storage.begin("esphome");
  }
  return s_ready;
}

static void format_key(uint32_t key, char *buffer, size_t len) {
  snprintf(buffer, len, "%08lx", static_cast<unsigned long>(key));
}

void setup_preferences() {
  static BouffaloPreferences preferences;
  global_preferences = &preferences;
}

BouffaloPreferences *get_preferences() { return static_cast<BouffaloPreferences *>(global_preferences); }

bool BouffaloPreferenceBackend::save(const uint8_t *src, size_t len) {
  if (len != this->data.size()) {
    return false;
  }
  if (!this->loaded || memcmp(src, this->data.data(), len) != 0) {
    memcpy(this->data.data(), src, len);
    this->dirty = true;
    this->loaded = true;
  }
  return true;
}

bool BouffaloPreferenceBackend::load(uint8_t *dest, size_t len) {
  if (len != this->data.size()) {
    return false;
  }
  if (!this->loaded) {
    this->loaded = get_preferences()->load_from_key(this->key, this->data.data(), len);
  }
  if (!this->loaded) {
    return false;
  }
  memcpy(dest, this->data.data(), len);
  return true;
}

ESPPreferenceObject BouffaloPreferences::make_preference(size_t length, uint32_t key, bool in_flash) {
  for (auto *entry : this->entries_) {
    if (entry->key == key) {
      return entry->data.size() == length ? ESPPreferenceObject(entry) : ESPPreferenceObject();
    }
  }
  auto *entry = new BouffaloPreferenceBackend(key, length);  // NOLINT(cppcoreguidelines-owning-memory)
  this->entries_.push_back(entry);
  return ESPPreferenceObject(entry);
}

bool BouffaloPreferences::load_from_key(uint32_t key, uint8_t *data, size_t len) {
  if (this->reset_ || !open_storage()) {
    return false;
  }
  char name[9];
  format_key(key, name, sizeof(name));
  return s_storage.getBytesLength(name) == len && s_storage.getBytes(name, data, len) == len;
}

bool BouffaloPreferences::sync() {
  if (this->reset_) {
    return false;
  }
  bool success = true;
  for (auto *entry : this->entries_) {
    if (!entry->dirty) {
      continue;
    }
    char name[9];
    format_key(entry->key, name, sizeof(name));
    if (open_storage() && s_storage.putBytes(name, entry->data.data(), entry->data.size()) == entry->data.size()) {
      entry->dirty = false;
    } else {
      success = false;
    }
  }
  return success;
}

bool BouffaloPreferences::reset() {
  if (!open_storage() || !s_storage.clear()) {
    return false;
  }
  this->reset_ = true;
  for (auto *entry : this->entries_) {
    entry->dirty = false;
  }
  return true;
}

}  // namespace esphome::bouffalo

#endif  // USE_BOUFFALO
