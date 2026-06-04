"""Sentinel by SourceBox — Home Assistant integration.

One config entry per Command Center org: a coordinator polls the org-wide
camera + status API, and a background task streams motion events (SSE) and
dispatches them to per-camera motion binary_sensors.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .api import SentinelApiError, SentinelAuthError, SentinelClient
from .const import CONF_API_KEY, CONF_BASE_URL, DOMAIN, motion_signal
from .coordinator import SentinelCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

# Backoff between motion-SSE reconnect attempts after the stream drops.
_MOTION_RECONNECT_SECONDS = 10
# Longer backoff when the stream is rejected for auth (revoked key): the
# coordinator's own poll drives the actual reauth + entry reload (which
# cancels this task), so the listener just needs to stop hammering the CC
# with a 401 every few seconds in the meantime.
_MOTION_AUTH_BACKOFF_SECONDS = 60


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sentinel from a config entry."""
    session = async_get_clientsession(hass)
    client = SentinelClient(session, entry.data[CONF_BASE_URL], entry.data[CONF_API_KEY])

    coordinator = SentinelCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Long-lived motion listener. async_create_background_task is cancelled
    # automatically when the entry unloads.
    entry.async_create_background_task(
        hass, _motion_listener(hass, coordinator), name=f"{DOMAIN}_motion_{entry.entry_id}"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry (also cancels the motion background task)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _motion_listener(hass: HomeAssistant, coordinator: SentinelCoordinator) -> None:
    """Consume the motion SSE forever, redispatching events to entities.

    The server holds the stream open with a 25s keepalive; if it drops
    (deploy, network blip, key revoked) we reconnect with a short backoff.
    A 401 is logged and retried — the coordinator's own auth failure path
    is what surfaces a revoked key to the user via reauth.
    """
    while True:
        try:
            async for event in coordinator.client.async_iter_motion():
                camera_id = event.get("camera_id")
                if camera_id:
                    async_dispatcher_send(hass, motion_signal(camera_id), event)
        except asyncio.CancelledError:
            raise
        except SentinelAuthError as err:
            # Revoked key. SentinelAuthError subclasses SentinelApiError, so it
            # MUST be caught first. The coordinator surfaces the reauth; we just
            # back off hard instead of looping on a 401 every 10s until then.
            _LOGGER.debug("Motion stream auth rejected (%s); backing off", err)
            await asyncio.sleep(_MOTION_AUTH_BACKOFF_SECONDS)
            continue
        except SentinelApiError as err:
            _LOGGER.debug("Motion stream dropped (%s); reconnecting", err)
        except Exception:  # noqa: BLE001 — never let the listener die silently
            _LOGGER.exception("Unexpected error in motion listener; reconnecting")
        await asyncio.sleep(_MOTION_RECONNECT_SECONDS)
