"""Camera entities — one per Sentinel camera, video LAN-direct."""

from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
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
        lambda cid: [SentinelCamera(coordinator, cid)],
    )


class SentinelCamera(SentinelCameraMixin, CoordinatorEntity, Camera):
    """A single camera. Stills via the snapshot API, live video LAN-direct."""

    _attr_name = None  # entity name follows the camera (device) name

    def __init__(self, coordinator, camera_id: str) -> None:
        # Init both bases explicitly — Camera.__init__ sets up its own
        # attributes that CoordinatorEntity.__init__ won't.
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._camera_id = camera_id
        self._attr_unique_id = f"{DOMAIN}_{camera_id}_camera"
        self._attr_supported_features = CameraEntityFeature.STREAM

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        return await self.coordinator.client.async_get_snapshot(self._camera_id)

    async def stream_source(self) -> str | None:
        stream = self._cam.get("stream") or {}
        # LAN-direct HLS when the node is reachable; proxy_url is reserved for
        # a future off-LAN path (CC Phase 2b) and is null today. None here
        # means "no live stream right now" — stills still work.
        return stream.get("local_url") or stream.get("proxy_url")
