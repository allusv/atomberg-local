"""Sensor platform: which transport is active, and BLE signal strength."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AtombergCoordinator
from .entity import AtombergEntity, setup_atomberg_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    def build(coordinator: AtombergCoordinator, device_id: str, _device) -> list:
        return [
            AtombergConnectionSensor(coordinator, device_id),
            AtombergRssiSensor(coordinator, device_id),
        ]

    setup_atomberg_platform(hass, entry, async_add_entities, build)


class AtombergConnectionSensor(AtombergEntity, SensorEntity):
    """Active control transport: wifi / ble / offline."""

    _attr_name = "Connection"
    _attr_translation_key = "connection"
    _attr_icon = "mdi:transit-connection-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["wifi", "ble", "offline"]

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("connection")

    @property
    def available(self) -> bool:
        return self._device_id in self.coordinator.manager.devices

    @property
    def native_value(self) -> str:
        return self.device.connection

    @property
    def extra_state_attributes(self) -> dict:
        d = self.device
        return {
            "provisioned": d.is_provisioned,
            "wifi_ip": d.wifi_ip,
            "wifi_available": d.wifi_available,
            "ble_available": d.ble_available,
        }


class AtombergRssiSensor(AtombergEntity, SensorEntity):
    """BLE signal strength."""

    _attr_name = "BLE signal"
    _attr_translation_key = "ble_rssi"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: AtombergCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = self._unique_id("ble_rssi")

    @property
    def available(self) -> bool:
        return self._device_id in self.coordinator.manager.devices

    @property
    def native_value(self) -> int | None:
        return self.device.ble_rssi
