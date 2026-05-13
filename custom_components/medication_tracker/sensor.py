"""Sensor platform for Medication Tracker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATORS, DOMAIN, SIGNAL_MEDICATIONS_UPDATED
from .coordinator import MedicationTrackerCoordinator
from .models import MedicationDefinition


@dataclass(frozen=True, slots=True)
class MedicationSensorDescription:
    """Description for a medication attribute sensor."""

    key: str
    name: str
    icon: str
    value_fn: Callable[[dict[str, Any]], Any]


ATTRIBUTE_SENSORS: tuple[MedicationSensorDescription, ...] = (
    MedicationSensorDescription(
        "medication_name",
        "Medication name",
        "mdi:label",
        lambda attrs: attrs.get("medication_name"),
    ),
    MedicationSensorDescription(
        "dose", "Dose", "mdi:cup-water", lambda attrs: attrs.get("dose")
    ),
    MedicationSensorDescription(
        "schedule_type",
        "Schedule type",
        "mdi:calendar-clock",
        lambda attrs: attrs.get("schedule_type"),
    ),
    MedicationSensorDescription(
        "due_times",
        "Due times",
        "mdi:clock-outline",
        lambda attrs: ", ".join(attrs.get("due_times") or []),
    ),
    MedicationSensorDescription(
        "next_due",
        "Next due",
        "mdi:calendar-arrow-right",
        lambda attrs: attrs.get("next_due"),
    ),
    MedicationSensorDescription(
        "last_taken",
        "Last taken",
        "mdi:check-circle-outline",
        lambda attrs: attrs.get("last_taken"),
    ),
    MedicationSensorDescription(
        "taken_today",
        "Taken today",
        "mdi:check",
        lambda attrs: _yes_no(attrs.get("taken_today")),
    ),
    MedicationSensorDescription(
        "required_today",
        "Required today",
        "mdi:calendar-check",
        lambda attrs: _yes_no(attrs.get("required_today")),
    ),
    MedicationSensorDescription(
        "doses_due_today",
        "Doses due today",
        "mdi:counter",
        lambda attrs: attrs.get("doses_due_today"),
    ),
    MedicationSensorDescription(
        "doses_taken_today",
        "Doses taken today",
        "mdi:counter",
        lambda attrs: attrs.get("doses_taken_today"),
    ),
    MedicationSensorDescription(
        "remaining_doses_today",
        "Remaining doses today",
        "mdi:counter",
        lambda attrs: attrs.get("remaining_doses_today"),
    ),
    MedicationSensorDescription(
        "missed_doses_today",
        "Missed doses today",
        "mdi:alert-circle-outline",
        lambda attrs: attrs.get("missed_doses_today"),
    ),
    MedicationSensorDescription(
        "skipped_doses_today",
        "Skipped doses today",
        "mdi:skip-next-circle-outline",
        lambda attrs: attrs.get("skipped_doses_today"),
    ),
    MedicationSensorDescription(
        "cycle_day",
        "Cycle day",
        "mdi:sync",
        lambda attrs: attrs.get("cycle_day"),
    ),
    MedicationSensorDescription(
        "cycle_status",
        "Cycle status",
        "mdi:sync-circle",
        lambda attrs: attrs.get("cycle_status"),
    ),
    MedicationSensorDescription(
        "grace_period_minutes",
        "Grace period",
        "mdi:timer-sand",
        lambda attrs: attrs.get("grace_period_minutes"),
    ),
    MedicationSensorDescription(
        "notes", "Notes", "mdi:note-text-outline", lambda attrs: attrs.get("notes")
    ),
)


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
            new_entities.extend(
                MedicationAttributeSensor(coordinator, medication, description)
                for description in ATTRIBUTE_SENSORS
            )
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
        return medication_device_info(
            self.medication_id, self.medication, self._attr_name
        )

    async def async_added_to_hass(self) -> None:
        """Persist the HA entity id for services and event payloads."""
        await super().async_added_to_hass()
        await self.coordinator.store.async_set_entity_id(
            self.medication_id, self.entity_id
        )
        await self.coordinator.async_refresh_and_reschedule()


class MedicationTrackerEntity(CoordinatorEntity[MedicationTrackerCoordinator]):
    """Shared base marker for medication tracker entities."""


class MedicationAttributeSensor(
    CoordinatorEntity[MedicationTrackerCoordinator], SensorEntity
):
    """A sensor exposing a single medication status attribute."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: MedicationTrackerCoordinator,
        medication: MedicationDefinition,
        description: MedicationSensorDescription,
    ) -> None:
        """Initialize the attribute sensor."""
        super().__init__(coordinator)
        self.medication_id = medication.id
        self.description = description
        self._attr_unique_id = f"{medication.id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon

    @property
    def medication(self) -> MedicationDefinition | None:
        """Return the current medication definition."""
        return self.coordinator.store.get_medication(self.medication_id)

    @property
    def available(self) -> bool:
        """Return true if the medication and value exist."""
        return (
            super().available
            and self.medication is not None
            and self.native_value not in (None, "")
        )

    @property
    def native_value(self) -> Any:
        """Return the attribute value as a sensor state."""
        status = self.coordinator.data.get(self.medication_id)
        if status is None:
            return None
        return self.description.value_fn(status.attributes)

    @property
    def device_info(self) -> dict:
        """Return the medication device info."""
        return medication_device_info(self.medication_id, self.medication)


def medication_device_info(
    medication_id: str,
    medication: MedicationDefinition | None,
    fallback_name: str | None = None,
) -> dict:
    """Return shared medication device info."""
    return {
        "identifiers": {(DOMAIN, medication_id)},
        "name": medication.name if medication else fallback_name or medication_id,
        "manufacturer": "Medication Tracker",
        "model": "Medication schedule",
    }


def _yes_no(value: Any) -> str | None:
    """Return a friendly yes/no string for boolean sensor states."""
    if value is None:
        return None
    return "Yes" if bool(value) else "No"
