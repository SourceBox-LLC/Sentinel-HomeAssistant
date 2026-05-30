"""Sensors — per-CloudNode storage + version diagnostics."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    @callback
    def _sync() -> None:
        items = (coordinator.data.get("status") or {}).get("nodes", {}).get("items", [])
        new = []
        for node in items:
            node_id = node.get("node_id")
            if not node_id or node_id in known:
                continue
            known.add(node_id)
            new.append(SentinelNodeStorageSensor(coordinator, node_id))
            new.append(SentinelNodeVersionSensor(coordinator, node_id))
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))


class _NodeEntity(CoordinatorEntity):
    """Base for entities on a CloudNode device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, node_id: str) -> None:
        super().__init__(coordinator)
        self._node_id = node_id

    @property
    def _node(self) -> dict:
        items = (self.coordinator.data.get("status") or {}).get("nodes", {}).get(
            "items", []
        )
        for node in items:
            if node.get("node_id") == self._node_id:
                return node
        return {}

    @property
    def device_info(self) -> DeviceInfo:
        node = self._node
        return DeviceInfo(
            identifiers={(DOMAIN, f"node:{self._node_id}")},
            name=node.get("name") or self._node_id,
            manufacturer=MANUFACTURER,
            model="Sentinel CloudNode",
            sw_version=node.get("version"),
        )


class SentinelNodeStorageSensor(_NodeEntity, SensorEntity):
    """Recording storage used on the node, in GB."""

    _attr_name = "Storage used"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, node_id: str) -> None:
        super().__init__(coordinator, node_id)
        self._attr_unique_id = f"{DOMAIN}_node_{node_id}_storage_used"

    @property
    def native_value(self) -> float | None:
        used = (self._node.get("storage") or {}).get("used_bytes")
        if used is None:
            return None
        return round(used / 1_000_000_000, 2)

    @property
    def extra_state_attributes(self) -> dict:
        storage = self._node.get("storage") or {}
        return {
            "disk_total_bytes": storage.get("disk_total_bytes"),
            "disk_free_bytes": storage.get("disk_free_bytes"),
            "configured_max_bytes": storage.get("max_bytes"),
        }


class SentinelNodeVersionSensor(_NodeEntity, SensorEntity):
    """The node's reported CloudNode version."""

    _attr_name = "Version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, node_id: str) -> None:
        super().__init__(coordinator, node_id)
        self._attr_unique_id = f"{DOMAIN}_node_{node_id}_version"

    @property
    def native_value(self) -> str | None:
        return self._node.get("version")
