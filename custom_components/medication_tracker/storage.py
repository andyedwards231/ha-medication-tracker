"""Persistent storage for Medication Tracker."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_HISTORY_RETENTION_DAYS,
    DOSE_STATUS_PENDING,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import DoseEvent, MedicationDefinition


class MedicationTrackerStore:
    """Async wrapper around Home Assistant storage helpers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True
        )
        self.medications: dict[str, MedicationDefinition] = {}
        self.dose_events: dict[str, DoseEvent] = {}
        self.fired_event_keys: set[str] = set()
        self.retention_days = DEFAULT_HISTORY_RETENTION_DAYS

    async def async_load(self) -> None:
        """Load persisted medication tracker data."""
        data = await self._store.async_load()
        if not data:
            return
        self.retention_days = int(data.get("retention_days", DEFAULT_HISTORY_RETENTION_DAYS))
        self.medications = {
            item["id"]: MedicationDefinition.from_dict(item)
            for item in data.get("medications", [])
        }
        self.dose_events = {
            item["id"]: DoseEvent.from_dict(item) for item in data.get("dose_events", [])
        }
        self.fired_event_keys = set(data.get("fired_event_keys", []))

    async def async_save(self) -> None:
        """Persist medication tracker data."""
        await self._store.async_save(
            {
                "retention_days": self.retention_days,
                "medications": [
                    medication.to_dict() for medication in self.medications.values()
                ],
                "dose_events": [event.to_dict() for event in self.dose_events.values()],
                "fired_event_keys": sorted(self.fired_event_keys),
            }
        )

    async def async_cleanup(self, now: datetime | None = None) -> None:
        """Remove history and event markers older than the retention period."""
        now = now or dt_util.now()
        cutoff = now - timedelta(days=self.retention_days)
        changed = False
        for event_id, event in list(self.dose_events.items()):
            scheduled = dt_util.parse_datetime(event.scheduled_for)
            if scheduled is None:
                continue
            if scheduled.tzinfo is None:
                scheduled = dt_util.as_local(dt_util.as_utc(scheduled))
            else:
                scheduled = dt_util.as_local(scheduled)
            if scheduled < cutoff:
                del self.dose_events[event_id]
                changed = True

        retained_keys: set[str] = set()
        cutoff_date = cutoff.date()
        for key in self.fired_event_keys:
            match = re.search(r"\d{4}-\d{2}-\d{2}", key)
            if match is None:
                retained_keys.add(key)
                continue
            try:
                key_date = datetime.fromisoformat(match.group(0)).date()
            except ValueError:
                retained_keys.add(key)
                continue
            if key_date >= cutoff_date:
                retained_keys.add(key)
        if retained_keys != self.fired_event_keys:
            self.fired_event_keys = retained_keys
            changed = True

        if changed:
            await self.async_save()

    def get_medication(self, medication_id: str) -> MedicationDefinition | None:
        """Return a medication by id."""
        return self.medications.get(medication_id)

    async def async_upsert_medication(self, medication: MedicationDefinition) -> None:
        """Create or update a medication."""
        self.medications[medication.id] = medication
        await self.async_save()

    async def async_remove_medication(self, medication_id: str) -> MedicationDefinition | None:
        """Remove a medication and its stored dose history."""
        removed = self.medications.pop(medication_id, None)
        if removed is None:
            return None
        for event_id, event in list(self.dose_events.items()):
            if event.medication_id == medication_id:
                del self.dose_events[event_id]
        self.fired_event_keys = {
            key for key in self.fired_event_keys if f":{medication_id}:" not in key
        }
        await self.async_save()
        return removed

    async def async_set_entity_id(self, medication_id: str, entity_id: str) -> None:
        """Persist an entity id for event payloads and service lookup."""
        medication = self.medications.get(medication_id)
        if medication is None or medication.entity_id == entity_id:
            return
        medication.entity_id = entity_id
        medication.updated_at = dt_util.now().isoformat()
        await self.async_save()

    def event_for(self, medication_id: str, scheduled_for: datetime) -> DoseEvent | None:
        """Return an event by medication and scheduled datetime."""
        return self.dose_events.get(DoseEvent.make_id(medication_id, scheduled_for))

    async def async_set_dose_event(
        self,
        medication_id: str,
        scheduled_for: datetime,
        status: str,
        acted_at: datetime | None = None,
        source: str | None = None,
        note: str | None = None,
    ) -> DoseEvent:
        """Create or replace a stored dose event."""
        now = dt_util.now().isoformat()
        event_id = DoseEvent.make_id(medication_id, scheduled_for)
        existing = self.dose_events.get(event_id)
        event = DoseEvent(
            id=event_id,
            medication_id=medication_id,
            scheduled_for=scheduled_for.isoformat(),
            status=status,
            acted_at=acted_at.isoformat() if acted_at else None,
            source=source,
            note=note,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.dose_events[event_id] = event
        await self.async_save()
        return event

    async def async_ensure_pending_event(
        self, medication_id: str, scheduled_for: datetime
    ) -> DoseEvent:
        """Ensure a pending event exists for a due dose."""
        existing = self.event_for(medication_id, scheduled_for)
        if existing is not None:
            return existing
        return await self.async_set_dose_event(
            medication_id, scheduled_for, DOSE_STATUS_PENDING
        )

    async def async_remove_dose_event(self, event_id: str) -> DoseEvent | None:
        """Remove a dose event."""
        event = self.dose_events.pop(event_id, None)
        if event is not None:
            await self.async_save()
        return event

    def has_fired(self, key: str) -> bool:
        """Return whether an event key has already fired."""
        return key in self.fired_event_keys

    async def async_mark_fired(self, key: str) -> None:
        """Persist that an event key has fired."""
        if key in self.fired_event_keys:
            return
        self.fired_event_keys.add(key)
        await self.async_save()
