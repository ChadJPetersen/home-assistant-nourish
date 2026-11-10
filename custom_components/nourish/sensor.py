"""Dynamic sensors for nutrients observed in Nourish's goals response."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import NourishCoordinator

# Assign units only to known nutrient names, never assume unknown ones.
NUTRIENTS = {
    "CALORIES": ("Calories", "kcal"),
    "CALORIE": ("Calories", "kcal"),
    "ENERGY": ("Energy", "kcal"),
    "PROTEIN": ("Protein", "g"),
    "CARBS": ("Carbs", "g"),
    "CARBOHYDRATES": ("Carbohydrates", "g"),
    "FAT": ("Fat", "g"),
    "TOTAL_FAT": ("Total fat", "g"),
    "FIBER": ("Fiber", "g"),
    "DIETARY_FIBER": ("Dietary fiber", "g"),
    "SUGAR": ("Sugar", "g"),
    "SODIUM": ("Sodium", "mg"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create status sensors and nutrient sensors for observed subtypes."""
    coordinator: NourishCoordinator = hass.data[DOMAIN][entry.entry_id]
    seen: set[str] = set()

    @callback
    def discover() -> None:
        """Create entities if a later sync discovers new nutrient categories."""
        if not coordinator.data:
            return
        new = []
        for subtype in coordinator.data.nutrients:
            if subtype in seen:
                continue
            seen.add(subtype)
            for kind in ("progress", "goal"):
                new.append(NourishNutrientSensor(coordinator, entry, subtype, kind))
        if new:
            async_add_entities(new)

    async_add_entities([NourishLastSyncSensor(coordinator, entry)])
    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class NourishNutrientSensor(CoordinatorEntity[NourishCoordinator], SensorEntity):
    """Current-day progress or target for one observed nutrient."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NourishCoordinator, entry: ConfigEntry, subtype: str, kind: str
    ) -> None:
        super().__init__(coordinator)
        self._subtype = subtype
        self._kind = kind
        name, unit = NUTRIENTS.get(subtype, (subtype.replace("_", " ").title(), None))
        self._attr_name = f"{name} {'today' if kind == 'progress' else 'goal'}"
        self._attr_unique_id = f"{entry.entry_id}_{subtype}_{kind}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = "mdi:chart-line" if kind == "progress" else "mdi:target"
        if kind == "progress":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Nourish Nutrition",
            manufacturer="Community integration",
        )

    @property
    def native_value(self) -> float | None:
        """Report unknown rather than assuming missing data is zero."""
        data = self.coordinator.data
        if data is None or data.day != dt_util.now().date():
            return None
        nutrient = data.nutrients.get(self._subtype)
        if nutrient is None:
            return None
        return nutrient.progress if self._kind == "progress" else nutrient.goal


class NourishLastSyncSensor(CoordinatorEntity[NourishCoordinator], SensorEntity):
    """Timestamp for the most recent successful goals request."""

    _attr_has_entity_name = True
    _attr_name = "Last sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: NourishCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_sync"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Nourish Nutrition",
            manufacturer="Community integration",
        )

    @property
    def native_value(self):
        """Read the last successful update time."""
        return self.coordinator.data.fetched_at if self.coordinator.data else None
