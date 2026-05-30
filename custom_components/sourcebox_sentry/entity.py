"""Shared entity helpers for camera-scoped entities."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER


class SentinelCameraMixin:
    """``_cam`` / device_info / availability for camera-scoped entities.

    The concrete entity sets ``self.coordinator`` (via CoordinatorEntity) and
    ``self._camera_id``. Mixin defines no ``__init__`` so the MRO init flows
    cleanly through CoordinatorEntity (and Camera, for the camera entity).
    """

    _attr_has_entity_name = True
    _camera_id: str

    @property
    def _cam(self) -> dict:
        return self.coordinator.data.get("cameras", {}).get(self._camera_id, {})

    @property
    def device_info(self) -> DeviceInfo:
        cam = self._cam
        info = DeviceInfo(
            identifiers={(DOMAIN, self._camera_id)},
            name=cam.get("name") or self._camera_id,
            manufacturer=MANUFACTURER,
            model="Sentinel Camera",
        )
        node_id = cam.get("node_id")
        if node_id:
            # Link the camera device under its CloudNode device (created by
            # the sensor platform with the same identifier).
            info["via_device"] = (DOMAIN, f"node:{node_id}")
        return info

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._camera_id in self.coordinator.data.get("cameras", {})
        )


@callback
def add_camera_entities(
    coordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[str], Iterable],
) -> None:
    """Add entities per camera, including cameras that appear on later
    coordinator refreshes (a node coming online, a camera being added in the
    Command Center) — no HA reconfiguration needed."""
    known: set[str] = set()

    @callback
    def _sync() -> None:
        new = []
        for camera_id in list(coordinator.data.get("cameras", {})):
            if camera_id not in known:
                known.add(camera_id)
                new.extend(build(camera_id))
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(coordinator.async_add_listener(_sync))
