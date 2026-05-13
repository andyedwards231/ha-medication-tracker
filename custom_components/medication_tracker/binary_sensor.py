"""Binary sensor platform for Medication Tracker."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATORS, DOMAIN, SIGNAL_MEDICATIONS_UPDATED
from .coordinator import MedicationTrackerCoordinator
from .models import MedicationDefinition
from .sensor import medication_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medication Tracker binary sensors."""
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
            new_entities.append(MedicationDueBinarySensor(coordinator, medication))
        if new_entities:
            async_add_entities(new_entities)

    async_add_missing_entities()
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_MEDICATIONS_UPDATED, async_add_missing_entities
        )
    )


class MedicationDueBinarySensor(
    CoordinatorEntity[MedicationTrackerCoordinator], BinarySensorEntity
):
    """Binary sensor that is on when a medication needs attention."""

    _attr_has_entity_name = True
    _attr_name = "Needs attention"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: MedicationTrackerCoordinator,
        medication: MedicationDefinition,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.medication_id = medication.id
        self._attr_unique_id = f"{medication.id}_needs_attention"
        self._attr_icon = "mdi:pill-alert"

    @property
    def medication(self) -> MedicationDefinition | None:
        """Return the current medication definition."""
        return self.coordinator.store.get_medication(self.medication_id)

    @property
    def available(self) -> bool:
        """Return true if the medication still exists."""
        return super().available and self.medication is not None

    @property
    def is_on(self) -> bool | None:
        """Return true when the medication is due or missed."""
        status = self.coordinator.data.get(self.medication_id)
        return status.is_due_or_missed if status else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return medication status attributes."""
        status = self.coordinator.data.get(self.medication_id)
        return status.attributes if status else {}

    @property
    def device_info(self) -> dict:
        """Return the medication device info."""
        return medication_device_info(self.medication_id, self.medication)
