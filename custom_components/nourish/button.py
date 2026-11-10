"""Manual Sync Now button for Nourish."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NourishCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add one manual synchronization button."""
    async_add_entities([NourishSyncButton(hass.data[DOMAIN][entry.entry_id], entry)])


class NourishSyncButton(CoordinatorEntity[NourishCoordinator], ButtonEntity):
    """Request an update without waiting until 11:56 PM."""

    _attr_has_entity_name = True
    _attr_name = "Sync now"
    _attr_icon = "mdi:sync"

    def __init__(self, coordinator: NourishCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_sync_now"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Nourish Nutrition",
            manufacturer="Community integration",
        )

    async def async_press(self) -> None:
        """Fetch current data on demand."""
        await self.coordinator.async_request_refresh()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError("Nourish sync failed; see integration status")
