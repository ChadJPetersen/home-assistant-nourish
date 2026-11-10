"""Experimental Nourish Nutrition integration."""

from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN, SERVICE_SYNC_NOW
from .coordinator import NourishCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the manual refresh action once."""
    hass.data.setdefault(DOMAIN, {})

    async def async_sync_now(call: ServiceCall) -> None:
        """Manually synchronize the configured integration."""
        coordinators: dict[str, NourishCoordinator] = hass.data.get(DOMAIN, {})
        if not coordinators:
            raise HomeAssistantError("Configure Nourish Nutrition before syncing")
        coordinator = next(iter(coordinators.values()))
        await coordinator.async_request_refresh()
        if not coordinator.last_update_success:
            raise HomeAssistantError("Nourish sync failed; see integration status")

    hass.services.async_register(DOMAIN, SERVICE_SYNC_NOW, async_sync_now)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initialize OAuth client, sensors, button and scheduled synchronization."""
    coordinator = NourishCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def sync_at_night(now: datetime) -> None:
        """Sync each night at 23:56 in Home Assistant's configured timezone."""
        hass.async_create_task(coordinator.async_request_refresh())

    @callback
    def advance_local_day(now: datetime) -> None:
        """Do not carry yesterday's totals into the next local day."""
        if coordinator.data is not None:
            coordinator.async_set_updated_data(coordinator.data)

    entry.async_on_unload(
        async_track_time_change(hass, sync_at_night, hour=23, minute=56, second=0)
    )
    entry.async_on_unload(
        async_track_time_change(hass, advance_local_day, hour=0, minute=0, second=0)
    )
    _LOGGER.debug("Nourish Nutrition configured for 23:56 local synchronization")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Stop scheduled tasks and remove entities."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    entry.async_unload_callbacks()
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True
