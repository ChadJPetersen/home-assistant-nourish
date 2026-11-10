"""Home Assistant coordination of scheduled and manual Nourish reads."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NourishAuthError, NourishClient, NourishConnectionError
from .const import CONF_REFRESH_TOKEN
from .models import DailyGoals, parse_goals_response

_LOGGER = logging.getLogger(__name__)


class NourishCoordinator(DataUpdateCoordinator[DailyGoals]):
    """Refresh on demand, at startup and through the nightly scheduled task."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Nourish Nutrition",
            update_interval=None,
        )
        self.entry = entry
        self.client = NourishClient(
            async_get_clientsession(hass),
            dict(entry.data),
            on_token_rotation=self._save_rotated_token,
        )

    async def _save_rotated_token(self, token: str) -> None:
        """Persist the replacement immediately to avoid using a spent token."""
        if self.entry.data.get(CONF_REFRESH_TOKEN) != token:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_REFRESH_TOKEN: token},
            )

    async def _async_update_data(self) -> DailyGoals:
        """Read real-time data from Nourish, never logging sensitive responses."""
        try:
            raw = await self.client.async_fetch_goals()
            return parse_goals_response(raw, dt_util.now().date(), dt_util.utcnow())
        except NourishAuthError as err:
            raise ConfigEntryAuthFailed("Nourish credentials need to be renewed") from err
        except (NourishConnectionError, ValueError) as err:
            raise UpdateFailed(str(err)) from err
