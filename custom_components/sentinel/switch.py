"""Switch entities — per-camera continuous recording toggle."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import SentinelCameraMixin, add_camera_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_camera_entities(
        coordinator,
        entry,
        async_add_entities,
        lambda cid: [SentinelRecordingSwitch(coordinator, cid)],
    )


class SentinelRecordingSwitch(SentinelCameraMixin, CoordinatorEntity, SwitchEntity):
    """Continuous recording on/off — mirrors the dashboard record button."""

    _attr_name = "Recording"
    _attr_icon = "mdi:record-rec"

    def __init__(self, coordinator, camera_id: str) -> None:
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_unique_id = f"{DOMAIN}_{camera_id}_recording"

    @property
    def is_on(self) -> bool:
        return bool(self._cam.get("recording"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_recording(self._camera_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.async_set_recording(self._camera_id, False)
        await self.coordinator.async_request_refresh()
