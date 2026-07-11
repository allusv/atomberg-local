"""Home Assistant integration constants."""

from homeassistant.const import Platform

DOMAIN = "atomberg_local"

PLATFORMS = [
    Platform.FAN,
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.SENSOR,
]

SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device"

CONF_BLE_SCAN_INTERVAL = "ble_scan_interval"
DEFAULT_UPDATE_INTERVAL = 30  # seconds

MANUFACTURER = "Atomberg"
