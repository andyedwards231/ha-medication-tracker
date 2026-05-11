"""Sensor platform for Medication Tracker."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATORS, DOMAIN, SIGNAL_MEDICATIONS_UPDATED
from .coordinator import MedicationTrackerCoordinator
from .models import MedicationDefinition


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medication Tracker sensors."""
    coordinator: MedicationTrackerCoordinator = hass.data[DOMAIN][DATA_COORDINATORS][
        entry.entry_id
    ]
    known: set[str] = set()

    @callback
    def async_add_missing_entities() -> None:
        new_entities = []
        for medication in coordinator.store.medications.values():
            if medication.id in known:
                continue
            known.add(medication.id)
            new_entities.append(MedicationSensor(coordinator, medication))
        if new_entities:
            async_add_entities(new_entities)

    async_add_missing_entities()
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_MEDICATIONS_UPDATED, async_add_missing_entities
        )
    )


class MedicationSensor(CoordinatorEntity[MedicationTrackerCoordinator], SensorEntity):
    """Main medication status sensor."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: MedicationTrackerCoordinator,
        medication: MedicationDefinition,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.medication_id = medication.id
        self._attr_unique_id = f"{medication.id}_status"
        self._attr_name = medication.name
        self._attr_icon = medication.icon or "mdi:pill"

    @property
    def medication(self) -> MedicationDefinition | None:
        """Return the current medication definition."""
        return self.coordinator.store.get_medication(self.medication_id)

    @property
    def available(self) -> bool:
        """Return true if the medication still exists."""
        return super().available and self.medication is not None

    @property
    def native_value(self) -> str | None:
        """Return the friendly medication state."""
        status = self.coordinator.data.get(self.medication_id)
        return status.state if status else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return medication status attributes."""
        status = self.coordinator.data.get(self.medication_id)
        return status.attributes if status else {}

    @property
    def device_info(self) -> dict:
        """Return the medication device info."""
        medication = self.medication
        return {
            "identifiers": {(DOMAIN, self.medication_id)},
            "name": medication.name if medication else self._attr_name,
            "manufacturer": "Local",
            "model": "Medication schedule",
        }

    async def async_added_to_hass(self) -> None:
        """Persist the HA entity id for services and event payloads."""
        await super().async_added_to_hass()
        await self.coordinator.store.async_set_entity_id(
            self.medication_id, self.entity_id
        )
        await self.coordinator.async_refresh_and_reschedule()


class MedicationTrackerEntity(CoordinatorEntity[MedicationTrackerCoordinator]):
    """Shared base marker for medication tracker entities."""
