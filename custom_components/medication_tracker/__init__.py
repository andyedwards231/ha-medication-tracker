"""Medication Tracker custom integration."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CYCLE_OFF_DAYS,
    CONF_CYCLE_ON_DAYS,
    CONF_CYCLE_START_DATE,
    CONF_DOSE,
    CONF_DUE_TIMES,
    CONF_GRACE_PERIOD_MINUTES,
    CONF_ICON,
    CONF_MEDICATION_ID,
    CONF_NOTE,
    CONF_NOTES,
    CONF_REASON,
    CONF_SCHEDULE_TYPE,
    CONF_SCHEDULED_FOR,
    CONF_SOURCE,
    CONF_TAKEN_AT,
    CONF_WEEKDAYS,
    DATA_COORDINATORS,
    DEFAULT_GRACE_PERIOD_MINUTES,
    DOMAIN,
    PLATFORMS,
    SCHEDULE_TYPES,
    SIGNAL_MEDICATIONS_UPDATED,
)
from .coordinator import MedicationTrackerCoordinator
from .models import MedicationDefinition
from .schedule import normalize_due_times, parse_local_datetime
from .storage import MedicationTrackerStore

MedicationTrackerConfigEntry = ConfigEntry


ENTITY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_MEDICATION_ID): cv.string,
        vol.Optional(CONF_SCHEDULED_FOR): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

MARK_TAKEN_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_TAKEN_AT): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
        vol.Optional(CONF_NOTE): cv.string,
    }
)

SKIP_DOSE_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_REASON): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

MEDICATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MEDICATION_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_DOSE): cv.string,
        vol.Required(CONF_SCHEDULE_TYPE): vol.In(SCHEDULE_TYPES),
        vol.Required(CONF_DUE_TIMES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_NOTES): cv.string,
        vol.Optional(CONF_WEEKDAYS): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_CYCLE_START_DATE): cv.string,
        vol.Optional(CONF_CYCLE_ON_DAYS): vol.Coerce(int),
        vol.Optional(CONF_CYCLE_OFF_DAYS): vol.Coerce(int),
        vol.Optional(
            CONF_GRACE_PERIOD_MINUTES, default=DEFAULT_GRACE_PERIOD_MINUTES
        ): vol.Coerce(int),
        vol.Optional(CONF_ICON): cv.icon,
    }
)

UPDATE_MEDICATION_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_MEDICATION_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_DOSE): cv.string,
        vol.Optional(CONF_SCHEDULE_TYPE): vol.In(SCHEDULE_TYPES),
        vol.Optional(CONF_DUE_TIMES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_NOTES): cv.string,
        vol.Optional(CONF_WEEKDAYS): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_CYCLE_START_DATE): cv.string,
        vol.Optional(CONF_CYCLE_ON_DAYS): vol.Coerce(int),
        vol.Optional(CONF_CYCLE_OFF_DAYS): vol.Coerce(int),
        vol.Optional(CONF_GRACE_PERIOD_MINUTES): vol.Coerce(int),
        vol.Optional(CONF_ICON): cv.icon,
    }
)

REMOVE_MEDICATION_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_MEDICATION_ID): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, _: dict[str, Any]) -> bool:
    """Set up integration-wide service actions."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_COORDINATORS, {})

    async def async_get_coordinator() -> MedicationTrackerCoordinator:
        coordinators: dict[str, MedicationTrackerCoordinator] = hass.data[DOMAIN][
            DATA_COORDINATORS
        ]
        if not coordinators:
            raise HomeAssistantError("Medication Tracker has no loaded config entry")
        return next(iter(coordinators.values()))

    def medication_from_call(
        coordinator: MedicationTrackerCoordinator, call: ServiceCall
    ) -> MedicationDefinition:
        medication_id = call.data.get(CONF_MEDICATION_ID)
        if medication_id:
            medication = coordinator.store.get_medication(medication_id)
            if medication is None:
                raise HomeAssistantError(f"Medication not found: {medication_id}")
            return medication

        entity_ids = call.data.get(ATTR_ENTITY_ID)
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        if entity_ids:
            medication = coordinator.medication_for_entity(entity_ids[0])
            if medication is not None:
                return medication
        raise HomeAssistantError("Provide a medication sensor entity or medication_id")

    async def async_mark_taken(call: ServiceCall) -> None:
        coordinator = await async_get_coordinator()
        medication = medication_from_call(coordinator, call)
        taken_at = parse_local_datetime(call.data.get(CONF_TAKEN_AT))
        await coordinator.async_mark_taken(
            medication,
            taken_at=taken_at,
            scheduled_for=call.data.get(CONF_SCHEDULED_FOR),
            source=call.data.get(CONF_SOURCE),
            note=call.data.get(CONF_NOTE),
        )

    async def async_undo_taken(call: ServiceCall) -> None:
        coordinator = await async_get_coordinator()
        medication = medication_from_call(coordinator, call)
        await coordinator.async_undo_taken(
            medication, scheduled_for=call.data.get(CONF_SCHEDULED_FOR)
        )

    async def async_skip_dose(call: ServiceCall) -> None:
        coordinator = await async_get_coordinator()
        medication = medication_from_call(coordinator, call)
        await coordinator.async_skip_dose(
            medication,
            scheduled_for=call.data.get(CONF_SCHEDULED_FOR),
            reason=call.data.get(CONF_REASON),
            source=call.data.get(CONF_SOURCE),
        )

    async def async_add_medication(call: ServiceCall) -> None:
        coordinator = await async_get_coordinator()
        medication = medication_from_service(call.data)
        await coordinator.async_add_or_update_medication(medication)
        async_dispatcher_send(hass, SIGNAL_MEDICATIONS_UPDATED)

    async def async_update_medication(call: ServiceCall) -> None:
        coordinator = await async_get_coordinator()
        existing = medication_from_call(coordinator, call)
        data = dict(existing.to_dict())
        data.update(
            {key: value for key, value in call.data.items() if key != ATTR_ENTITY_ID}
        )
        data[CONF_MEDICATION_ID] = existing.id
        medication = medication_from_service(data, existing_id=existing.id)
        medication.entity_id = existing.entity_id
        medication.created_at = existing.created_at
        await coordinator.async_add_or_update_medication(medication)
        async_dispatcher_send(hass, SIGNAL_MEDICATIONS_UPDATED)

    async def async_remove_medication(call: ServiceCall) -> None:
        coordinator = await async_get_coordinator()
        medication = medication_from_call(coordinator, call)
        entity_id = medication.entity_id
        device_identifier = (DOMAIN, medication.id)
        await coordinator.async_remove_medication(medication.id)

        entity_registry = er.async_get(hass)
        if entity_id:
            registry_entry = entity_registry.async_get(entity_id)
            if registry_entry:
                entity_registry.async_remove(entity_id)

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(identifiers={device_identifier})
        if device:
            device_registry.async_remove_device(device.id)

        async_dispatcher_send(hass, SIGNAL_MEDICATIONS_UPDATED)

    hass.services.async_register(
        DOMAIN, "mark_taken", async_mark_taken, schema=MARK_TAKEN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "undo_taken", async_undo_taken, schema=ENTITY_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "skip_dose", async_skip_dose, schema=SKIP_DOSE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "add_medication", async_add_medication, schema=MEDICATION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "remove_medication",
        async_remove_medication,
        schema=REMOVE_MEDICATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "update_medication",
        async_update_medication,
        schema=UPDATE_MEDICATION_SCHEMA,
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MedicationTrackerConfigEntry
) -> bool:
    """Set up Medication Tracker from a config entry."""
    store = MedicationTrackerStore(hass)
    coordinator = MedicationTrackerCoordinator(hass, store)
    await coordinator.async_config_entry_first_refresh()

    if entry.data.get("initial_medication") and not store.medications:
        medication = medication_from_service(entry.data["initial_medication"])
        await store.async_upsert_medication(medication)
        await coordinator.async_request_refresh()
    if entry.data.get("initial_medication"):
        data = dict(entry.data)
        data.pop("initial_medication", None)
        hass.config_entries.async_update_entry(entry, data=data)

    await _async_import_pending_options(hass, entry, coordinator)

    hass.data.setdefault(DOMAIN, {}).setdefault(DATA_COORDINATORS, {})[
        entry.entry_id
    ] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MedicationTrackerConfigEntry
) -> bool:
    """Unload a Medication Tracker config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN][DATA_COORDINATORS].pop(entry.entry_id)
        await coordinator.async_stop()
    return unload_ok


def medication_from_service(
    data: dict[str, Any], existing_id: str | None = None
) -> MedicationDefinition:
    """Create a medication definition from service/config flow data."""
    now = dt_util.now().isoformat()
    medication_id = existing_id or data.get(CONF_MEDICATION_ID) or uuid.uuid4().hex
    return MedicationDefinition(
        id=medication_id,
        name=data[CONF_NAME],
        dose=data[CONF_DOSE],
        schedule_type=data[CONF_SCHEDULE_TYPE],
        due_times=normalize_due_times(data.get(CONF_DUE_TIMES)),
        notes=data.get(CONF_NOTES),
        weekdays=[int(day) for day in data.get(CONF_WEEKDAYS, [])],
        cycle_start_date=data.get(CONF_CYCLE_START_DATE),
        cycle_on_days=data.get(CONF_CYCLE_ON_DAYS),
        cycle_off_days=data.get(CONF_CYCLE_OFF_DAYS),
        grace_period_minutes=int(
            data.get(CONF_GRACE_PERIOD_MINUTES, DEFAULT_GRACE_PERIOD_MINUTES)
        ),
        icon=data.get(CONF_ICON),
        created_at=data.get("created_at") or now,
        updated_at=now,
    )


async def _async_options_updated(
    hass: HomeAssistant, entry: MedicationTrackerConfigEntry
) -> None:
    """Import medications added through the options flow."""
    coordinator = hass.data[DOMAIN][DATA_COORDINATORS].get(entry.entry_id)
    if coordinator is not None:
        await _async_import_pending_options(hass, entry, coordinator)


async def _async_import_pending_options(
    hass: HomeAssistant,
    entry: MedicationTrackerConfigEntry,
    coordinator: MedicationTrackerCoordinator,
) -> None:
    """Create medications queued by the options flow."""
    pending = list(entry.options.get("pending_medications", []))
    if not pending:
        return
    for medication_data in pending:
        await coordinator.async_add_or_update_medication(
            medication_from_service(medication_data)
        )
    options = dict(entry.options)
    options["pending_medications"] = []
    hass.config_entries.async_update_entry(entry, options=options)
    async_dispatcher_send(hass, SIGNAL_MEDICATIONS_UPDATED)
