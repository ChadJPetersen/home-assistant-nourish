"""User-facing configuration and reauthentication flows."""

from __future__ import annotations

import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
import voluptuous as vol

from .api import NourishAuthError, NourishClient, NourishConnectionError
from .const import (
    CONF_CLIENT_ID,
    CONF_CONNECTION_DETAILS,
    CONF_DEVICE_TIME_ZONE,
    CONF_PATIENT_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .models import parse_goals_response


def parse_connection_details(value: str) -> dict[str, str]:
    """Decode the one-time JSON copied by the documented browser helper."""
    try:
        details = json.loads(value)
    except (ValueError, TypeError) as err:
        raise ValueError("Connection details must be JSON") from err
    if not isinstance(details, dict):
        raise ValueError("Connection details must be a JSON object")

    mapping = {
        "clientId": CONF_CLIENT_ID,
        "patientId": CONF_PATIENT_ID,
        "refreshToken": CONF_REFRESH_TOKEN,
        "deviceTimeZone": CONF_DEVICE_TIME_ZONE,
    }
    normalized = {}
    for browser_key, setting_key in mapping.items():
        item = details.get(browser_key)
        if isinstance(item, int) and not isinstance(item, bool) and browser_key == "patientId":
            item = str(item)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Missing {browser_key}")
        normalized[setting_key] = item.strip()

    if not re.fullmatch(r"[0-9]{1,30}", normalized[CONF_PATIENT_ID]):
        raise ValueError("Invalid patientId")
    try:
        ZoneInfo(normalized[CONF_DEVICE_TIME_ZONE])
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise ValueError("Unknown deviceTimeZone") from err
    return normalized


def _schema() -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_CONNECTION_DETAILS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
    })


class NourishConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure Nourish with a single secret paste."""

    VERSION = 1

    async def _validate(self, details: dict[str, str]) -> dict[str, str]:
        client = NourishClient(async_get_clientsession(self.hass), details)
        result = await client.async_fetch_goals()
        # Validate the contract at setup, rather than silently creating broken entities.
        from datetime import date, datetime, timezone
        parse_goals_response(result, date.today(), datetime.now(timezone.utc))
        return {**details, CONF_REFRESH_TOKEN: client.refresh_token}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                details = parse_connection_details(user_input[CONF_CONNECTION_DETAILS])
                details = await self._validate(details)
            except (ValueError, KeyError):
                errors["base"] = "invalid_details"
            except NourishAuthError:
                errors["base"] = "invalid_auth"
            except NourishConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(details[CONF_PATIENT_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Nourish Nutrition", data=details)
        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)

    async def async_step_reauth(self, entry_data: dict) -> FlowResult:
        """Start a credential replacement without losing existing entities."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                details = parse_connection_details(user_input[CONF_CONNECTION_DETAILS])
                if details[CONF_PATIENT_ID] != entry.data[CONF_PATIENT_ID]:
                    errors["base"] = "different_account"
                else:
                    details = await self._validate(details)
            except (ValueError, KeyError):
                errors["base"] = "invalid_details"
            except NourishAuthError:
                errors["base"] = "invalid_auth"
            except NourishConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if not errors:
                    await self.async_set_unique_id(details[CONF_PATIENT_ID])
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        entry, data_updates=details
                    )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_schema(), errors=errors
        )
