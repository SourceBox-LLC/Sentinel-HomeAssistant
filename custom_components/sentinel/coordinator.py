"""DataUpdateCoordinator — polls camera + status state for all entities."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SentinelApiError, SentinelAuthError, SentinelClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SentinelCoordinator(DataUpdateCoordinator):
    """Polls /cameras + /status; entities read shared state from ``data``.

    ``data`` shape: ``{"cameras": {camera_id: {...}}, "status": {...}}``.
    Motion is delivered out-of-band over SSE (see __init__.py), not here.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: SentinelClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict:
        try:
            cameras = await self.client.async_get_cameras()
            status = await self.client.async_get_status()
        except SentinelAuthError as err:
            # Triggers HA's reauth flow so the user can paste a fresh key.
            raise ConfigEntryAuthFailed(str(err)) from err
        except SentinelApiError as err:
            raise UpdateFailed(str(err)) from err

        return {
            "cameras": {c["id"]: c for c in cameras if c.get("id")},
            "status": status,
        }
