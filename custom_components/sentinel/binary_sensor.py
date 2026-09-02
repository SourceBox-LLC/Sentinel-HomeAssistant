"""Binary sensors — per-camera motion (SSE) and connectivity."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MOTION_RESET_SECONDS, motion_signal
from .entity import SentinelCameraMixin, add_camera_entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_camera_entities(
        coordinator,
        entry,
        async_add_entities,
        lambda cid: [
            SentinelMotionSensor(coordinator, cid),
            SentinelConnectivitySensor(coordinator, cid),
        ],
    )


class SentinelMotionSensor(SentinelCameraMixin, CoordinatorEntity, BinarySensorEntity):
    """Motion, driven by the org-wide motion SSE.

    The feed is event-only, so the entity latches ``on`` on each event and
    self-resets after ``MOTION_RESET_SECONDS``."""

    _attr_name = "Motion"
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, coordinator, camera_id: str) -> None:
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_unique_id = f"{DOMAIN}_{camera_id}_motion"
        self._attr_is_on = False
        self._cancel_reset = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, motion_signal(self._camera_id), self._on_motion
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_reset is not None:
            self._cancel_reset()
            self._cancel_reset = None
        await super().async_will_remove_from_hass()

    @callback
    def _on_motion(self, _event: dict) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()
        if self._cancel_reset is not None:
            self._cancel_reset()
        self._cancel_reset = async_call_later(
            self.hass, MOTION_RESET_SECONDS, self._reset
        )

    @callback
    def _reset(self, _now) -> None:
        self._cancel_reset = None
        self._attr_is_on = False
        self.async_write_ha_state()


class SentinelConnectivitySensor(
    SentinelCameraMixin, CoordinatorEntity, BinarySensorEntity
):
    """Whether the camera is currently reporting as online."""

    _attr_name = "Connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, camera_id: str) -> None:
        super().__init__(coordinator)
        self._camera_id = camera_id
        self._attr_unique_id = f"{DOMAIN}_{camera_id}_online"

    @property
    def is_on(self) -> bool:
        return bool(self._cam.get("online"))
