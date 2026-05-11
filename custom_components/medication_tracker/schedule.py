"""Schedule helpers for Medication Tracker."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DOSE_STATUS_MISSED,
    DOSE_STATUS_SKIPPED,
    DOSE_STATUS_TAKEN,
    SCHEDULE_CYCLE,
    SCHEDULE_DAILY,
    SCHEDULE_TIMES_PER_DAY,
    SCHEDULE_WEEKDAYS,
    SCHEDULE_WEEKLY,
    STATUS_DUE_NOW,
    STATUS_MISSED,
    STATUS_NOT_REQUIRED_TODAY,
    STATUS_PARTIALLY_TAKEN,
    STATUS_TAKE_LATER_TODAY,
    STATUS_TAKEN_TODAY,
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
            if scheduled < now and offset > 0:
                continue
            if not event_is_handled(event_for_schedule(medication.id, scheduled, events)):
                if scheduled >= now or scheduled.date() == local_day:
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
        for scheduled in scheduled_datetimes_for_date(
            hass, medication, dt_util.as_local(now).date()
        ):
            event = event_for_schedule(medication.id, scheduled, events)
            if event_is_handled(event):
                continue
            missed_at = scheduled + timedelta(minutes=medication.grace_period_minutes)
            if scheduled > now:
                candidates.append(scheduled)
            if missed_at > now:
                candidates.append(missed_at)
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
    unhandled_today = [
        scheduled
        for scheduled in today_schedules
        if not event_is_handled(event_for_schedule(medication.id, scheduled, events))
    ]
    due = [scheduled for scheduled in unhandled_today if scheduled <= now]
    if due:
        return min(due)
    if unhandled_today:
        return min(unhandled_today)
    return next_due_datetime(hass, medication, events, now, search_days=370)


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
    """Compute the display state and attributes for a medication."""
    now = now or local_now()
    local_day = dt_util.as_local(now).date()
    required_today = is_required_on_date(medication, local_day)
    today_schedules = scheduled_datetimes_for_date(hass, medication, local_day)
    cycle_day, cycle_status = cycle_info(medication, local_day)

    taken_events = [
        event
        for event in events.values()
        if event.medication_id == medication.id
        and event.status == DOSE_STATUS_TAKEN
        and parse_local_datetime(event.scheduled_for)
        and parse_local_datetime(event.scheduled_for).date() == local_day
    ]
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

    missed = 0
    skipped = 0
    handled = 0
    due_now = False
    future_unhandled = False

    for scheduled in today_schedules:
        event = event_for_schedule(medication.id, scheduled, events)
        if event and event.status == DOSE_STATUS_TAKEN:
            handled += 1
            continue
        if event and event.status == DOSE_STATUS_SKIPPED:
            skipped += 1
            handled += 1
            continue
        if event and event.status == DOSE_STATUS_MISSED:
            missed += 1
            handled += 1
            continue

        missed_at = scheduled + timedelta(minutes=medication.grace_period_minutes)
        if now > missed_at:
            missed += 1
        elif scheduled <= now:
            due_now = True
        else:
            future_unhandled = True

    doses_due_today = len(today_schedules)
    doses_taken_today = len(taken_events)
    remaining = max(doses_due_today - handled - missed, 0)

    next_due = next_due_datetime(hass, medication, events, now)

    if not required_today:
        state = STATUS_NOT_REQUIRED_TODAY
    elif missed > 0:
        state = STATUS_MISSED
    elif due_now:
        state = STATUS_DUE_NOW
    elif handled > 0 and (future_unhandled or remaining > 0):
        state = STATUS_PARTIALLY_TAKEN
    elif future_unhandled:
        state = STATUS_TAKE_LATER_TODAY
    elif doses_due_today > 0 and handled == doses_due_today:
        state = STATUS_TAKEN_TODAY
    else:
        state = STATUS_UNKNOWN

    attributes: dict[str, Any] = {
        "medication_name": medication.name,
        "dose": medication.dose,
        "schedule_type": medication.schedule_type,
        "due_times": normalize_due_times(medication.due_times),
        "next_due": next_due.isoformat() if next_due else None,
        "last_taken": last_taken,
        "taken_today": doses_taken_today > 0,
        "required_today": required_today,
        "doses_due_today": doses_due_today,
        "doses_taken_today": doses_taken_today,
        "remaining_doses_today": remaining,
        "missed_doses_today": missed,
        "skipped_doses_today": skipped,
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
        is_due_or_missed=state in {STATUS_DUE_NOW, STATUS_MISSED},
    )
