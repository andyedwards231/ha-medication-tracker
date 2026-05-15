"""Button platform for Medication Tracker."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATORS, DOMAIN, SIGNAL_MEDICATIONS_UPDATED
from .coordinator import MedicationTrackerCoordinator
from .models import MedicationDefinition
from .sensor import medication_device_info


@dataclass(frozen=True, slots=True)
class MedicationButtonDescription:
    """Description for a medication action button."""

    key: str
    name: str
    icon: str
    press_fn: Callable[
        [MedicationTrackerCoordinator, MedicationDefinition], Awaitable[None]
    ]


async def _mark_taken(
    coordinator: MedicationTrackerCoordinator, medication: MedicationDefinition
) -> None:
    """Mark the next dose as taken."""
    await coordinator.async_mark_taken(medication, source="Button")


async def _skip_dose(
    coordinator: MedicationTrackerCoordinator, medication: MedicationDefinition
) -> None:
    """Skip the next dose."""
    await coordinator.async_skip_dose(medication, source="Button")


async def _mark_not_taken(
    coordinator: MedicationTrackerCoordinator, medication: MedicationDefinition
) -> None:
    """Undo the latest taken dose."""
    await coordinator.async_undo_taken(medication)


async def _reset_today(
    coordinator: MedicationTrackerCoordinator, medication: MedicationDefinition
) -> None:
    """Reset today's dose history for this medication."""
    await coordinator.async_reset_today(medication)


BUTTONS: tuple[MedicationButtonDescription, ...] = (
    MedicationButtonDescription(
        "mark_taken", "Mark taken", "mdi:pill", _mark_taken
    ),
    MedicationButtonDescription(
        "skip_dose", "Skip dose", "mdi:skip-next", _skip_dose
    ),
    MedicationButtonDescription(
        "mark_not_taken", "Mark not taken", "mdi:undo", _mark_not_taken
    ),
    MedicationButtonDescription(
        "reset_today", "Reset today", "mdi:restore", _reset_today
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medication Tracker buttons."""
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
            new_entities.extend(
                MedicationActionButton(coordinator, medication, description)
                for description in BUTTONS
            )
        if new_entities:
            async_add_entities(new_entities)

    async_add_missing_entities()
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, SIGNAL_MEDICATIONS_UPDATED, async_add_missing_entities
        )
    )


class MedicationActionButton(
    CoordinatorEntity[MedicationTrackerCoordinator], ButtonEntity
):
    """Button that performs a medication action."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MedicationTrackerCoordinator,
        medication: MedicationDefinition,
        description: MedicationButtonDescription,
    ) -> None:
        """Initialize the button."""
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
        """Return true if the medication still exists."""
        return super().available and self.medication is not None

    @property
    def device_info(self) -> dict:
        """Return the medication device info."""
        return medication_device_info(self.medication_id, self.medication)

    async def async_press(self) -> None:
        """Handle the button press."""
        medication = self.medication
        if medication is None:
            raise HomeAssistantError("Medication not found")
        await self.description.press_fn(self.coordinator, medication)
