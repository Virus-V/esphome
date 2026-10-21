#include "wifi_component.h"

#if defined(USE_WIFI) && defined(USE_BOUFFALO)

#include <WiFi.h>

#include "esphome/core/application.h"

namespace esphome::wifi {

namespace {
// WiFiComponent is a singleton in ESPHome. Keeping the two transient state
// bits local avoids platform-specific fields in the shared generated header.
bool s_scan_pending{false};
bool s_connecting{false};
}  // namespace

void WiFiComponent::wifi_pre_setup_() { WiFi.startAsync(); }

bool WiFiComponent::wifi_sta_pre_setup_() {
  if (!WiFi.startAsync())
    return false;

  // startAsync() only queues the SDK initialization task. Wait for the WiFi
  // manager before the component state machine enters fast connect.
  static constexpr uint8_t READY_RETRIES = 200;
  for (uint8_t i = 0; i < READY_RETRIES && !WiFi.ready(); i++) {
    delay(10);
  }
  return WiFi.ready();
}

bool WiFiComponent::wifi_mode_(optional<bool> sta, optional<bool> ap) {
  if (ap.value_or(false))
    return false;
  if (!WiFi.ready())
    return WiFi.startAsync();
  return WiFi.mode(sta.value_or(true) ? WIFI_MODE_STA : WIFI_MODE_NULL);
}

bool WiFiComponent::wifi_apply_output_power_(float) { return false; }

bool WiFiComponent::wifi_apply_power_save_() { return this->power_save_ == WIFI_POWER_SAVE_NONE; }

bool WiFiComponent::wifi_apply_hostname_() { return WiFi.setHostname(App.get_name().c_str()); }

bool WiFiComponent::wifi_sta_ip_config_(const optional<ManualIP> &manual_ip) {
  if (manual_ip.has_value()) {
    return WiFi.config(static_cast<::IPAddress>(manual_ip->static_ip), static_cast<::IPAddress>(manual_ip->gateway),
                       static_cast<::IPAddress>(manual_ip->subnet), static_cast<::IPAddress>(manual_ip->dns1),
                       static_cast<::IPAddress>(manual_ip->dns2));
  }
  return WiFi.config(::IPAddress(static_cast<uint32_t>(0)), ::IPAddress(static_cast<uint32_t>(0)),
                     ::IPAddress(static_cast<uint32_t>(0)));
}

bool WiFiComponent::wifi_sta_connect_(const WiFiAP &ap) {
  if (!WiFi.ready())
    return false;
#ifdef USE_WIFI_MANUAL_IP
  if (!this->wifi_sta_ip_config_(ap.get_manual_ip()))
    return false;
#else
  if (!this->wifi_sta_ip_config_({}))
    return false;
#endif
  s_connecting = true;
  const bool started = WiFi.begin(ap.get_ssid().c_str(), ap.get_password().c_str(), ap.get_channel(),
                                  ap.has_bssid() ? ap.get_bssid().data() : nullptr) != WL_CONNECT_FAILED;
  if (!started) {
    s_connecting = false;
  }
  return started;
}

WiFiSTAConnectStatus WiFiComponent::wifi_sta_connect_status_() const {
  if (WiFi.status() == WL_CONNECTED && static_cast<uint32_t>(WiFi.localIP()) != 0)
    return WiFiSTAConnectStatus::CONNECTED;
  if (WiFi.status() == WL_IDLE_STATUS || s_connecting)
    return WiFiSTAConnectStatus::CONNECTING;
  return WiFiSTAConnectStatus::IDLE;
}

bool WiFiComponent::wifi_disconnect_() {
  s_connecting = false;
  return WiFi.disconnect();
}

bool WiFiComponent::wifi_scan_start_(bool) {
  if (!WiFi.ready())
    return false;
  this->scan_done_ = false;
  s_scan_pending = WiFi.scanNetworks(true) == -1;
  return s_scan_pending;
}

bool WiFiComponent::wifi_loop_() {
  if (!WiFi.ready())
    return false;
  if (WiFi.status() == WL_CONNECTED)
    s_connecting = false;

  if (s_scan_pending) {
    const int count = WiFi.scanComplete();
    if (count < 0)
      return true;
    s_scan_pending = false;
    ScanResultsLock lock(this);
    this->scan_result_.clear();
    if (this->scan_result_.try_init(count)) {
      for (int i = 0; i < count; i++) {
        auto ssid = WiFi.SSID(i);
        bssid_t bssid{};
        if (const auto *raw_bssid = WiFi.BSSID(i); raw_bssid != nullptr)
          memcpy(bssid.data(), raw_bssid, bssid.size());
        WiFiScanResult result{bssid,
                              ssid.c_str(),
                              ssid.length(),
                              WiFi.channel(i),
                              WiFi.RSSI(i),
                              WiFi.encryptionType(i) != WIFI_AUTH_OPEN,
                              ssid.length() == 0};
        this->scan_result_.push_back(result);
      }
    }
    this->scan_done_ = true;
  }
  return true;
}

network::IPAddresses WiFiComponent::wifi_sta_ip_addresses() {
  network::IPAddresses result{};
  result[0] = WiFi.localIP();
  return result;
}

bssid_t WiFiComponent::wifi_bssid() {
  bssid_t result{};
  if (const auto *bssid = WiFi.BSSID(); bssid != nullptr)
    memcpy(result.data(), bssid, result.size());
  return result;
}

const char *WiFiComponent::wifi_ssid_to(std::span<char, SSID_BUFFER_SIZE> buffer) {
  snprintf(buffer.data(), buffer.size(), "%s", WiFi.SSID().c_str());
  return buffer.data();
}

int8_t WiFiComponent::wifi_rssi() { return WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : WIFI_RSSI_DISCONNECTED; }

int32_t WiFiComponent::get_wifi_channel() { return WiFi.channel(); }

network::IPAddress WiFiComponent::wifi_subnet_mask_() { return WiFi.subnetMask(); }

network::IPAddress WiFiComponent::wifi_gateway_ip_() { return WiFi.gatewayIP(); }

network::IPAddress WiFiComponent::wifi_dns_ip_(int num) { return WiFi.dnsIP(num); }

}  // namespace esphome::wifi

#endif  // USE_WIFI && USE_BOUFFALO
