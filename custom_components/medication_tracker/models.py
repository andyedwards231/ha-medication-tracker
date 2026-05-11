"""Data models for Medication Tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import (
    DEFAULT_GRACE_PERIOD_MINUTES,
    DOSE_STATUS_PENDING,
    SCHEDULE_DAILY,
)


@dataclass(slots=True)
class MedicationDefinition:
    """A configured medication and its schedule."""

    id: str
    name: str
    dose: str
    schedule_type: str = SCHEDULE_DAILY
    due_times: list[str] = field(default_factory=list)
    notes: str | None = None
    weekdays: list[int] = field(default_factory=list)
    cycle_start_date: str | None = None
    cycle_on_days: int | None = None
    cycle_off_days: int | None = None
    grace_period_minutes: int = DEFAULT_GRACE_PERIOD_MINUTES
    icon: str | None = None
    entity_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MedicationDefinition":
        """Create a medication definition from stored data."""
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            dose=str(data.get("dose", "")),
            schedule_type=str(data.get("schedule_type", SCHEDULE_DAILY)),
            due_times=list(data.get("due_times") or []),
            notes=data.get("notes"),
            weekdays=[int(day) for day in data.get("weekdays") or []],
            cycle_start_date=data.get("cycle_start_date"),
            cycle_on_days=data.get("cycle_on_days"),
            cycle_off_days=data.get("cycle_off_days"),
            grace_period_minutes=int(
                data.get("grace_period_minutes", DEFAULT_GRACE_PERIOD_MINUTES)
            ),
            icon=data.get("icon"),
            entity_id=data.get("entity_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "name": self.name,
            "dose": self.dose,
            "schedule_type": self.schedule_type,
            "due_times": list(self.due_times),
            "notes": self.notes,
            "weekdays": list(self.weekdays),
            "cycle_start_date": self.cycle_start_date,
            "cycle_on_days": self.cycle_on_days,
            "cycle_off_days": self.cycle_off_days,
            "grace_period_minutes": self.grace_period_minutes,
            "icon": self.icon,
            "entity_id": self.entity_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class DoseEvent:
    """A single scheduled dose event."""

    id: str
    medication_id: str
    scheduled_for: str
    status: str = DOSE_STATUS_PENDING
    acted_at: str | None = None
    source: str | None = None
    note: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def make_id(cls, medication_id: str, scheduled_for: datetime | str) -> str:
        """Return a stable storage id for a medication schedule occurrence."""
        scheduled = (
            scheduled_for.isoformat()
            if isinstance(scheduled_for, datetime)
            else scheduled_for
        )
        return f"{medication_id}:{scheduled}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DoseEvent":
        """Create an event from stored data."""
        return cls(
            id=str(data["id"]),
            medication_id=str(data["medication_id"]),
            scheduled_for=str(data["scheduled_for"]),
            status=str(data.get("status", DOSE_STATUS_PENDING)),
            acted_at=data.get("acted_at"),
            source=data.get("source"),
            note=data.get("note"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "medication_id": self.medication_id,
            "scheduled_for": self.scheduled_for,
            "status": self.status,
            "acted_at": self.acted_at,
            "source": self.source,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class MedicationStatus:
    """Computed display state and attributes for a medication."""

    medication_id: str
    state: str
    attributes: dict[str, Any]
    is_due_or_missed: bool
