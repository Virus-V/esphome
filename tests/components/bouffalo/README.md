# Bouffalo test fixtures

The Bouffalo platform builds with the Arduino platform and SDK runtime from
[`arduino-bouffalo`](https://github.com/bouffalolab/arduino-bouffalo).

Install that repository as an Arduino hardware package before running a full
compile. The tests can discover the installed core automatically through
`arduino-cli`; `ESPHOME_ARDUINO_CLI_CONFIG` may point at a non-default
`arduino-cli` configuration file.

```sh
export ESPHOME_ARDUINO_CLI_CONFIG=/path/to/arduino-cli.yaml
esphome config tests/components/bouffalo/validate-gpio.bouffalo-ard.yaml
esphome compile tests/components/bouffalo/test-network.bouffalo-ard.yaml
```

`test-network.bouffalo-ard.yaml` is the compile fixture and therefore requires
the external Arduino core. `validate-gpio.bouffalo-ard.yaml` remains a
configuration-only test so schema coverage is useful even without the hardware
package installed.

Current scope:

- Wi-Fi station mode, DHCP or static IPv4, scanning, and hostname;
- GPIO input/output, pull-up/pull-down, open-drain emulation, and interrupts;
- native API and other components using ESPHome's lwIP socket backend;
- serial logging and UART flashing with the combined factory image.

mDNS is disabled by default because the SDK's current wl80211 netif does not
support the IGMP membership needed for multicast. SoftAP, Wi-Fi Enterprise,
and network OTA are not implemented yet.
