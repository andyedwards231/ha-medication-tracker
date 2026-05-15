"""Coordinator for Medication Tracker."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOSE_STATUS_MISSED,
    DOSE_STATUS_SKIPPED,
    DOSE_STATUS_TAKEN,
    EVENT_DUE,
    EVENT_MISSED,
    EVENT_NOT_REQUIRED_TODAY,
    EVENT_REQUIRED_TODAY,
    EVENT_SKIPPED,
    EVENT_TAKEN,
)
from .models import DoseEvent, MedicationDefinition, MedicationStatus
from .schedule import (
    compute_medication_status,
    cycle_info,
    dose_evaluations_for_date,
    event_is_handled,
    find_target_schedule,
    is_required_on_date,
    latest_taken_event,
    local_now,
    next_update_time,
)
from .storage import MedicationTrackerStore

_LOGGER = logging.getLogger(__name__)


class MedicationTrackerCoordinator(
    DataUpdateCoordinator[dict[str, MedicationStatus]]
):
    """Coordinate medication storage, schedule evaluation, and events."""

    def __init__(self, hass: HomeAssistant, store: MedicationTrackerStore) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Medication Tracker",
            always_update=False,
        )
        self.store = store
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._started = False

    async def _async_setup(self) -> None:
        """Load persisted data once before first refresh."""
        await self.store.async_load()
        await self.store.async_cleanup()

    async def _async_update_data(self) -> dict[str, MedicationStatus]:
        """Compute medication states and fire one-shot events."""
        now = local_now()
        if self._started:
            await self._async_process_events(now)
        return {
            medication.id: compute_medication_status(
                self.hass, medication, self.store.dose_events, now
            )
            for medication in self.store.medications.values()
        }

    async def async_start(self) -> None:
        """Start event processing and point-in-time refresh scheduling."""
        self._started = True
        await self.async_request_refresh()
        self._schedule_next_refresh()

    async def async_stop(self) -> None:
        """Stop scheduled callbacks."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    def _schedule_next_refresh(self) -> None:
        """Schedule the next refresh at a meaningful boundary."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

        next_refresh = next_update_time(
            self.hass,
            list(self.store.medications.values()),
            self.store.dose_events,
            local_now(),
        )
        if next_refresh is None:
            return
        self._unsub_timer = async_track_point_in_time(
            self.hass, self._handle_scheduled_refresh, next_refresh
        )

    @callback
    def _handle_scheduled_refresh(self, _: datetime) -> None:
        """Handle a scheduled refresh callback."""
        self.hass.async_create_task(self._async_scheduled_refresh())

    async def _async_scheduled_refresh(self) -> None:
        """Refresh data after a time boundary."""
        await self.async_request_refresh()
        self._schedule_next_refresh()

    async def async_refresh_and_reschedule(self) -> None:
        """Refresh entities and reschedule the next wake-up."""
        await self.async_request_refresh()
        self._schedule_next_refresh()

    async def _async_process_events(self, now: datetime) -> None:
        """Create dose history and fire Home Assistant events."""
        await self.store.async_cleanup(now)
        today = dt_util.as_local(now).date()
        for medication in list(self.store.medications.values()):
            required = is_required_on_date(medication, today)
            daily_key = (
                f"required:{medication.id}:{today.isoformat()}"
                if required
                else f"not_required:{medication.id}:{today.isoformat()}"
            )
            if not self.store.has_fired(daily_key):
                await self._async_fire_event(
                    EVENT_REQUIRED_TODAY if required else EVENT_NOT_REQUIRED_TODAY,
                    medication,
                    None,
                    None,
                )
                await self.store.async_mark_fired(daily_key)

            for dose in dose_evaluations_for_date(
                self.hass, medication, self.store.dose_events, today, now
            ):
                if dose.event and dose.event.status in {
                    DOSE_STATUS_TAKEN,
                    DOSE_STATUS_SKIPPED,
                }:
                    continue

                if dose.computed_missed:
                    event = await self.store.async_set_dose_event(
                        medication.id, dose.scheduled, DOSE_STATUS_MISSED
                    )
                    missed_key = f"missed:{medication.id}:{dose.scheduled.isoformat()}"
                    if not self.store.has_fired(missed_key):
                        await self._async_fire_event(
                            EVENT_MISSED, medication, dose.scheduled, event
                        )
                        await self.store.async_mark_fired(missed_key)
                    continue

                if dose.is_due_now(now) and not event_is_handled(dose.event):
                    event = await self.store.async_ensure_pending_event(
                        medication.id, dose.scheduled
                    )
                    due_key = f"due:{medication.id}:{dose.scheduled.isoformat()}"
                    if not self.store.has_fired(due_key):
                        await self._async_fire_event(
                            EVENT_DUE, medication, dose.scheduled, event
                        )
                        await self.store.async_mark_fired(due_key)

    async def _async_fire_event(
        self,
        event_type: str,
        medication: MedicationDefinition,
        scheduled_for: datetime | None,
        dose_event: DoseEvent | None,
    ) -> None:
        """Fire a medication tracker event."""
        local_day = dt_util.as_local(local_now()).date()
        cycle_day, cycle_status = cycle_info(medication, local_day)
        next_due = compute_medication_status(
            self.hass, medication, self.store.dose_events
        ).attributes.get("next_due")
        data: dict[str, Any] = {
            "entity_id": medication.entity_id,
            "medication_id": medication.id,
            "medication_name": medication.name,
            "dose": medication.dose,
            "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
            "due_time": scheduled_for.strftime("%H:%M") if scheduled_for else None,
            "next_due": next_due,
            "schedule_type": medication.schedule_type,
        }
        if cycle_day is not None:
            data["cycle_day"] = cycle_day
        if cycle_status is not None:
            data["cycle_status"] = cycle_status
        if dose_event and dose_event.source:
            data["source"] = dose_event.source
        if dose_event and dose_event.note:
            data["note"] = dose_event.note

        self.hass.bus.async_fire(event_type, data)

    def medication_for_entity(self, entity_id: str | None) -> MedicationDefinition | None:
        """Return the medication linked to an entity id."""
        if entity_id is None:
            return None
        for medication in self.store.medications.values():
            if medication.entity_id == entity_id:
                return medication
        return None

    async def async_mark_taken(
        self,
        medication: MedicationDefinition,
        taken_at: datetime | None = None,
        scheduled_for: str | None = None,
        source: str | None = None,
        note: str | None = None,
    ) -> DoseEvent:
        """Mark the next relevant dose as taken."""
        acted_at = taken_at or local_now()
        scheduled = find_target_schedule(
            self.hass, medication, self.store.dose_events, acted_at, scheduled_for
        )
        if scheduled is None:
            raise ValueError("No scheduled dose found")
        event = await self.store.async_set_dose_event(
            medication.id,
            scheduled,
            DOSE_STATUS_TAKEN,
            acted_at=acted_at,
            source=source,
            note=note,
        )
        await self._async_fire_event(EVENT_TAKEN, medication, scheduled, event)
        await self.async_refresh_and_reschedule()
        return event

    async def async_undo_taken(
        self, medication: MedicationDefinition, scheduled_for: str | None = None
    ) -> DoseEvent:
        """Undo the latest or selected taken dose."""
        event = latest_taken_event(medication.id, self.store.dose_events, scheduled_for)
        if event is None:
            raise ValueError("No taken dose found")
        removed = await self.store.async_remove_dose_event(event.id)
        await self.async_refresh_and_reschedule()
        return removed or event

    async def async_skip_dose(
        self,
        medication: MedicationDefinition,
        scheduled_for: str | None = None,
        reason: str | None = None,
        source: str | None = None,
    ) -> DoseEvent:
        """Mark the next relevant dose as skipped."""
        now = local_now()
        scheduled = find_target_schedule(
            self.hass, medication, self.store.dose_events, now, scheduled_for
        )
        if scheduled is None:
            raise ValueError("No scheduled dose found")
        event = await self.store.async_set_dose_event(
            medication.id,
            scheduled,
            DOSE_STATUS_SKIPPED,
            acted_at=now,
            source=source,
            note=reason,
        )
        await self._async_fire_event(EVENT_SKIPPED, medication, scheduled, event)
        await self.async_refresh_and_reschedule()
        return event

    async def async_reset_today(self, medication: MedicationDefinition) -> int:
        """Clear today's dose records for a medication and recalculate state."""
        local_day = dt_util.as_local(local_now()).date()
        removed = await self.store.async_clear_medication_day(medication.id, local_day)
        await self.async_refresh_and_reschedule()
        return removed

    async def async_add_or_update_medication(
        self, medication: MedicationDefinition
    ) -> MedicationDefinition:
        """Create or update a medication and refresh entities."""
        await self.store.async_upsert_medication(medication)
        await self.async_refresh_and_reschedule()
        return medication

    async def async_remove_medication(self, medication_id: str) -> MedicationDefinition:
        """Remove a medication and refresh entities."""
        removed = await self.store.async_remove_medication(medication_id)
        if removed is None:
            raise ValueError("Medication not found")
        await self.async_refresh_and_reschedule()
        return removed
