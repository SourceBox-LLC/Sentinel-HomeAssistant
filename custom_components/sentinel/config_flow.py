"""Config + reauth flow for Sentinel by SourceBox."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SentinelApiError, SentinelAuthError, SentinelClient
from .const import CONF_API_KEY, CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate(hass, base_url: str, api_key: str) -> dict:
    """Validate URL + key against /status. Returns the status dict or raises."""
    client = SentinelClient(async_get_clientsession(hass), base_url, api_key)
    return await client.async_get_status()


class SentinelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup + reauth for a Command Center org."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = user_input[CONF_BASE_URL].rstrip("/")
            api_key = user_input[CONF_API_KEY].strip()
            try:
                status = await _validate(self.hass, base_url, api_key)
            except SentinelAuthError:
                errors["base"] = "invalid_auth"
            except SentinelApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Sentinel config")
                errors["base"] = "unknown"
            else:
                # One entry per org — the status payload carries org_id.
                org_id = status.get("org_id") or base_url
                await self.async_set_unique_id(org_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Sentinel",
                    data={CONF_BASE_URL: base_url, CONF_API_KEY: api_key},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Triggered when the coordinator hits a 401 (revoked/rotated key)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}
        if user_input is not None and entry is not None:
            base_url = entry.data[CONF_BASE_URL]
            api_key = user_input[CONF_API_KEY].strip()
            try:
                await _validate(self.hass, base_url, api_key)
            except SentinelAuthError:
                errors["base"] = "invalid_auth"
            except SentinelApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Sentinel reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
