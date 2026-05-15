"""Schedule helpers for Medication Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from math import ceil
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DOSE_STATUS_MISSED,
    DOSE_STATUS_PENDING,
    DOSE_STATUS_SKIPPED,
    DOSE_STATUS_TAKEN,
    SCHEDULE_CYCLE,
    SCHEDULE_DAILY,
    SCHEDULE_TIMES_PER_DAY,
    SCHEDULE_WEEKDAYS,
    SCHEDULE_WEEKLY,
    STATUS_NEXT_DOSE_DUE,
    STATUS_REQUIRED_NOW,
    STATUS_SKIPPED,
    STATUS_TAKEN,
    STATUS_MISSED,
    STATUS_NOT_REQUIRED_TODAY,
    STATUS_UNKNOWN,
)
from .models import DoseEvent, MedicationDefinition, MedicationStatus


def local_now() -> datetime:
    """Return Home Assistant's local timezone-aware now."""
    return dt_util.now()


def parse_local_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime and return it in Home Assistant local time."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return dt_util.as_local(dt_util.as_utc(parsed))
    return dt_util.as_local(parsed)


def parse_local_date(value: str | None) -> date | None:
    """Parse an ISO date."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_time(value: str) -> time | None:
    """Parse a HH:MM or HH:MM:SS time string."""
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        hour, minute = parts
        second = 0
    elif len(parts) == 3:
        hour, minute, second = parts
    else:
        return None
    try:
        return time(hour, minute, second)
    except ValueError:
        return None


def local_datetime_for_time(hass: HomeAssistant, day: date, due_time: str) -> datetime | None:
    """Return a timezone-aware local datetime for a schedule time."""
    parsed_time = parse_time(due_time)
    if parsed_time is None:
        return None
    timezone = dt_util.get_time_zone(hass.config.time_zone)
    if timezone is None:
        timezone = dt_util.DEFAULT_TIME_ZONE
    return datetime.combine(day, parsed_time, tzinfo=timezone)


def normalize_due_times(due_times: list[str] | tuple[str, ...] | None) -> list[str]:
    """Return valid, sorted time strings."""
    valid: list[str] = []
    for due_time in due_times or []:
        parsed = parse_time(str(due_time))
        if parsed is None:
            continue
        valid.append(parsed.strftime("%H:%M"))
    return sorted(dict.fromkeys(valid))


@dataclass(frozen=True, slots=True)
class DoseEvaluation:
    """Source-of-truth view of one scheduled dose occurrence."""

    scheduled: datetime
    event: DoseEvent | None
    status: str
    missed_at: datetime
    computed_missed: bool

    @property
    def is_terminal(self) -> bool:
        """Return whether this dose is no longer pending for today."""
        return self.status in {
            DOSE_STATUS_TAKEN,
            DOSE_STATUS_SKIPPED,
            DOSE_STATUS_MISSED,
        }

    def is_due_now(self, now: datetime) -> bool:
        """Return true when the dose is due and still inside its grace period."""
        return (
            self.status == DOSE_STATUS_PENDING
            and self.scheduled <= now < self.missed_at
        )

    def is_future(self, now: datetime) -> bool:
        """Return true when the dose is pending later today."""
        return self.status == DOSE_STATUS_PENDING and self.scheduled > now


def cycle_info(medication: MedicationDefinition, day: date) -> tuple[int | None, str | None]:
    """Return the 1-based cycle day and on/off status for a date."""
    if medication.schedule_type != SCHEDULE_CYCLE:
        return None, None
    start = parse_local_date(medication.cycle_start_date)
    on_days = medication.cycle_on_days or 0
    off_days = medication.cycle_off_days or 0
    cycle_length = on_days + off_days
    if start is None or on_days <= 0 or off_days < 0 or cycle_length <= 0:
        return None, None
    elapsed = (day - start).days
    if elapsed < 0:
        return None, "off"
    cycle_day = (elapsed % cycle_length) + 1
    return cycle_day, "on" if cycle_day <= on_days else "off"


def is_required_on_date(medication: MedicationDefinition, day: date) -> bool:
    """Return whether a medication is required on a date."""
    if medication.schedule_type in {SCHEDULE_DAILY, SCHEDULE_TIMES_PER_DAY}:
        return True
    if medication.schedule_type == SCHEDULE_WEEKDAYS:
        return day.weekday() in set(medication.weekdays)
    if medication.schedule_type == SCHEDULE_WEEKLY:
        weekdays = medication.weekdays or [0]
        return day.weekday() == weekdays[0]
    if medication.schedule_type == SCHEDULE_CYCLE:
        _, status = cycle_info(medication, day)
        return status == "on"
    return False


def scheduled_datetimes_for_date(
    hass: HomeAssistant, medication: MedicationDefinition, day: date
) -> list[datetime]:
    """Return scheduled dose datetimes for a local date."""
    if not is_required_on_date(medication, day):
        return []
    due_times = normalize_due_times(medication.due_times)
    return [
        scheduled
        for due_time in due_times
        if (scheduled := local_datetime_for_time(hass, day, due_time)) is not None
    ]


def event_for_schedule(
    medication_id: str, scheduled_for: datetime, events: dict[str, DoseEvent]
) -> DoseEvent | None:
    """Return the stored event for a schedule occurrence, if any."""
    return events.get(DoseEvent.make_id(medication_id, scheduled_for))


def event_is_handled(event: DoseEvent | None) -> bool:
    """Return true if a dose has a terminal status."""
    return event is not None and event.status in {
        DOSE_STATUS_TAKEN,
        DOSE_STATUS_SKIPPED,
        DOSE_STATUS_MISSED,
    }


def dose_evaluations_for_date(
    hass: HomeAssistant,
    medication: MedicationDefinition,
    events: dict[str, DoseEvent],
    day: date,
    now: datetime,
) -> list[DoseEvaluation]:
    """Evaluate every scheduled dose for one local date.

    This is the single source of truth for daily counters and status. Stored
    terminal records win; otherwise the current local time and grace period
    decide whether a dose is future, due now, or missed.
    """
    evaluations: list[DoseEvaluation] = []
    for scheduled in scheduled_datetimes_for_date(hass, medication, day):
        event = event_for_schedule(medication.id, scheduled, events)
        missed_at = scheduled + timedelta(minutes=medication.grace_period_minutes)
        if event_is_handled(event):
            status = event.status if event is not None else DOSE_STATUS_PENDING
            computed_missed = False
        elif now >= missed_at:
            status = DOSE_STATUS_MISSED
            computed_missed = True
        else:
            status = DOSE_STATUS_PENDING
            computed_missed = False
        evaluations.append(
            DoseEvaluation(
                scheduled=scheduled,
                event=event,
                status=status,
                missed_at=missed_at,
                computed_missed=computed_missed,
            )
        )
    return evaluations


def next_due_datetime(
    hass: HomeAssistant,
    medication: MedicationDefinition,
    events: dict[str, DoseEvent],
    now: datetime | None = None,
    search_days: int = 370,
) -> datetime | None:
    """Return the next unhandled scheduled dose."""
    now = now or local_now()
    local_day = dt_util.as_local(now).date()
    for offset in range(search_days + 1):
        day = local_day + timedelta(days=offset)
        for scheduled in scheduled_datetimes_for_date(hass, medication, day):
            if event_is_handled(event_for_schedule(medication.id, scheduled, events)):
                continue
            if scheduled > now:
                return scheduled
            missed_at = scheduled + timedelta(minutes=medication.grace_period_minutes)
            if scheduled <= now < missed_at:
                return scheduled
    return None


def next_update_time(
    hass: HomeAssistant,
    medications: list[MedicationDefinition],
    events: dict[str, DoseEvent],
    now: datetime | None = None,
) -> datetime | None:
    """Return the next useful time to refresh entities."""
    now = now or local_now()
    tomorrow = dt_util.as_local(now).date() + timedelta(days=1)
    candidates: list[datetime] = []
    midnight = local_datetime_for_time(hass, tomorrow, "00:00")
    if midnight is not None:
        candidates.append(midnight)

    for medication in medications:
        for dose in dose_evaluations_for_date(
            hass, medication, events, dt_util.as_local(now).date(), now
        ):
            if dose.is_terminal:
                continue
            if dose.scheduled > now:
                candidates.append(dose.scheduled)
            if dose.missed_at > now:
                candidates.append(dose.missed_at)
        next_due = next_due_datetime(hass, medication, events, now)
        if next_due is not None and next_due > now:
            candidates.append(next_due)

    future = [candidate for candidate in candidates if candidate > now]
    return min(future) if future else None


def find_target_schedule(
    hass: HomeAssistant,
    medication: MedicationDefinition,
    events: dict[str, DoseEvent],
    now: datetime,
    scheduled_for: str | None = None,
) -> datetime | None:
    """Find the scheduled occurrence a service action should apply to."""
    if scheduled_for:
        return parse_local_datetime(scheduled_for)

    today = dt_util.as_local(now).date()
    today_schedules = scheduled_datetimes_for_date(hass, medication, today)
    actionable_today = [
        scheduled
        for scheduled in today_schedules
        if dose_can_be_actioned(
            event_for_schedule(medication.id, scheduled, events)
        )
    ]
    due = [scheduled for scheduled in actionable_today if scheduled <= now]
    if due:
        return min(due)
    if actionable_today:
        return min(actionable_today)
    return next_due_datetime(hass, medication, events, now, search_days=370)


def dose_can_be_actioned(event: DoseEvent | None) -> bool:
    """Return true if a dose can still be taken or skipped."""
    return event is None or event.status in {DOSE_STATUS_MISSED, DOSE_STATUS_PENDING}


def latest_taken_event(
    medication_id: str, events: dict[str, DoseEvent], scheduled_for: str | None = None
) -> DoseEvent | None:
    """Return the latest taken event for a medication."""
    if scheduled_for:
        scheduled = parse_local_datetime(scheduled_for)
        if scheduled is None:
            return None
        event = events.get(DoseEvent.make_id(medication_id, scheduled))
        return event if event and event.status == DOSE_STATUS_TAKEN else None

    taken = [
        event
        for event in events.values()
        if event.medication_id == medication_id and event.status == DOSE_STATUS_TAKEN
    ]
    return max(taken, key=lambda event: event.acted_at or event.updated_at or "") if taken else None


def compute_medication_status(
    hass: HomeAssistant,
    medication: MedicationDefinition,
    events: dict[str, DoseEvent],
    now: datetime | None = None,
) -> MedicationStatus:
    """Compute today's status from schedule, records, local time, and grace."""
    now = now or local_now()
    local_day = dt_util.as_local(now).date()
    required_today = is_required_on_date(medication, local_day)
    doses = dose_evaluations_for_date(hass, medication, events, local_day, now)
    cycle_day, cycle_status = cycle_info(medication, local_day)

    taken_doses = [dose for dose in doses if dose.status == DOSE_STATUS_TAKEN]
    skipped_doses = [dose for dose in doses if dose.status == DOSE_STATUS_SKIPPED]
    missed_doses = [dose for dose in doses if dose.status == DOSE_STATUS_MISSED]
    due_now_doses = [dose for dose in doses if dose.is_due_now(now)]
    future_doses = [dose for dose in doses if dose.is_future(now)]
    pending_doses = [dose for dose in doses if dose.status == DOSE_STATUS_PENDING]

    last_taken_today = latest_acted_at(taken_doses)
    last_skipped_today = latest_acted_at(skipped_doses)
    last_taken = max(
        (
            event.acted_at
            for event in events.values()
            if event.medication_id == medication.id
            and event.status == DOSE_STATUS_TAKEN
            and event.acted_at
        ),
        default=None,
    )

    doses_required_today = len(doses)
    doses_taken_today = len(taken_doses)
    skipped = len(skipped_doses)
    missed = len(missed_doses)
    remaining = len(pending_doses)
    next_due = next_due_datetime(hass, medication, events, now)
    current_dose_status = current_status_key(
        required_today, doses, due_now_doses, missed_doses, future_doses
    )

    if not required_today:
        base_state = STATUS_NOT_REQUIRED_TODAY
    elif due_now_doses:
        base_state = STATUS_REQUIRED_NOW
    elif missed_doses:
        base_state = STATUS_MISSED
    elif taken_doses:
        base_state = STATUS_TAKEN
    elif skipped_doses:
        base_state = STATUS_SKIPPED
    elif future_doses:
        base_state = STATUS_NEXT_DOSE_DUE
    elif doses and not pending_doses:
        base_state = STATUS_TAKEN
    else:
        base_state = STATUS_UNKNOWN

    state = format_state(base_state, missed_doses, future_doses, next_due, now)
    next_dose_in = minutes_until(next_due, now)

    attributes: dict[str, Any] = {
        "medication_name": medication.name,
        "base_status": base_state,
        "display_status": state,
        "dose": medication.dose,
        "schedule_type": medication.schedule_type,
        "due_times": normalize_due_times(medication.due_times),
        "next_due": next_due.isoformat() if next_due else None,
        "next_due_time": _format_local_time(next_due),
        "next_dose_in": next_dose_in,
        "last_taken": last_taken,
        "last_taken_today": last_taken_today,
        "taken_today": doses_taken_today > 0,
        "required_today": required_today,
        "doses_required_today": doses_required_today,
        "doses_due_today": remaining,
        "doses_taken_today": doses_taken_today,
        "remaining_doses_today": remaining,
        "missed_doses_today": missed,
        "skipped_doses_today": skipped,
        "current_dose_status": current_dose_status,
        "current_scheduled_for": current_scheduled_for(
            due_now_doses, missed_doses, future_doses
        ),
        "daily_status_date": local_day.isoformat(),
        "grace_period_minutes": medication.grace_period_minutes,
        "notes": medication.notes,
    }
    if cycle_day is not None:
        attributes["cycle_day"] = cycle_day
    if cycle_status is not None:
        attributes["cycle_status"] = cycle_status

    return MedicationStatus(
        medication_id=medication.id,
        state=state,
        attributes=attributes,
        is_due_or_missed=base_state in {STATUS_REQUIRED_NOW, STATUS_MISSED},
    )


def latest_acted_at(doses: list[DoseEvaluation]) -> str | None:
    """Return the latest action timestamp from evaluated doses."""
    return max(
        (
            dose.event.acted_at
            for dose in doses
            if dose.event is not None and dose.event.acted_at
        ),
        default=None,
    )


def current_status_key(
    required_today: bool,
    doses: list[DoseEvaluation],
    due_now_doses: list[DoseEvaluation],
    missed_doses: list[DoseEvaluation],
    future_doses: list[DoseEvaluation],
) -> str:
    """Return a machine-friendly current daily dose status."""
    if not required_today:
        return "not_required"
    if due_now_doses:
        return "required_now"
    if missed_doses:
        return "missed"
    if future_doses:
        return "pending"
    if doses and all(dose.status == DOSE_STATUS_SKIPPED for dose in doses):
        return "skipped"
    if doses and all(dose.status == DOSE_STATUS_TAKEN for dose in doses):
        return "taken"
    if doses:
        return "completed"
    return "unknown"


def current_scheduled_for(
    due_now_doses: list[DoseEvaluation],
    missed_doses: list[DoseEvaluation],
    future_doses: list[DoseEvaluation],
) -> str | None:
    """Return the most relevant scheduled dose datetime for attributes."""
    for dose_list in (due_now_doses, missed_doses, future_doses):
        if dose_list:
            return dose_list[0].scheduled.isoformat()
    return None


def format_state(
    base_state: str,
    missed_doses: list[DoseEvaluation],
    future_doses: list[DoseEvaluation],
    next_due: datetime | None,
    now: datetime,
) -> str:
    """Return the user-facing medication state."""
    if base_state == STATUS_REQUIRED_NOW:
        return STATUS_REQUIRED_NOW
    if base_state == STATUS_NEXT_DOSE_DUE:
        next_today = future_doses[0].scheduled if future_doses else next_due
        return format_next_dose_phrase(next_today, now, capitalize=True) or base_state
    if base_state == STATUS_MISSED:
        late = missed_late_minutes(missed_doses[0], now) if missed_doses else None
        state = f"Missed, {late} mins late" if late is not None else STATUS_MISSED
        phrase = format_next_dose_phrase(next_due, now)
        return f"{state}, {phrase}" if phrase else state
    if base_state in {STATUS_TAKEN, STATUS_SKIPPED, STATUS_NOT_REQUIRED_TODAY}:
        phrase = format_next_dose_phrase(next_due, now)
        return f"{base_state}, {phrase}" if phrase else base_state
    return base_state


def missed_late_minutes(dose: DoseEvaluation, now: datetime) -> int:
    """Return minutes elapsed since the dose became missed."""
    seconds = (dt_util.as_local(now) - dt_util.as_local(dose.missed_at)).total_seconds()
    return max(0, ceil(seconds / 60))


def minutes_until(value: datetime | None, now: datetime) -> int | None:
    """Return whole minutes until a future dose, clamped at zero."""
    if value is None:
        return None
    seconds = (dt_util.as_local(value) - dt_util.as_local(now)).total_seconds()
    return max(0, ceil(seconds / 60))


def format_next_dose_phrase(
    value: datetime | None, now: datetime, *, capitalize: bool = False
) -> str | None:
    """Return compact next-dose text for the main sensor state."""
    if value is None:
        return None
    local_value = dt_util.as_local(value)
    local_now = dt_util.as_local(now)
    if local_value <= local_now:
        return None

    day_delta = (local_value.date() - local_now.date()).days
    if day_delta == 0:
        phrase = f"next dose at {local_value.strftime('%H:%M')}"
    elif day_delta == 1:
        phrase = "next dose tomorrow"
    elif 1 < day_delta < 7:
        phrase = f"next dose on {local_value.strftime('%A')}"
    else:
        phrase = f"next dose on {local_value.strftime('%d %b')}"

    return phrase[0].upper() + phrase[1:] if capitalize else phrase


def _format_local_time(value: datetime | None) -> str | None:
    """Format a datetime as local HH:MM."""
    if value is None:
        return None
    return dt_util.as_local(value).strftime("%H:%M")
