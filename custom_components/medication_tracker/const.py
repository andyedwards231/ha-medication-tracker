"""Constants for the Medication Tracker integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "medication_tracker"
NAME = "Medication Tracker"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

CONF_MEDICATION_ID = "medication_id"
CONF_DOSE = "dose"
CONF_DUE_TIMES = "due_times"
CONF_NOTES = "notes"
CONF_SCHEDULE_TYPE = "schedule_type"
CONF_WEEKDAYS = "weekdays"
CONF_CYCLE_START_DATE = "cycle_start_date"
CONF_CYCLE_ON_DAYS = "cycle_on_days"
CONF_CYCLE_OFF_DAYS = "cycle_off_days"
CONF_GRACE_PERIOD_MINUTES = "grace_period_minutes"
CONF_ICON = "icon"
CONF_TAKEN_AT = "taken_at"
CONF_SCHEDULED_FOR = "scheduled_for"
CONF_SOURCE = "source"
CONF_NOTE = "note"
CONF_REASON = "reason"

DEFAULT_GRACE_PERIOD_MINUTES = 60
DEFAULT_HISTORY_RETENTION_DAYS = 90

STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

DATA_COORDINATORS = "coordinators"

SIGNAL_MEDICATIONS_UPDATED = f"{DOMAIN}_medications_updated"

SCHEDULE_DAILY = "every_day"
SCHEDULE_TIMES_PER_DAY = "multiple_times_per_day"
SCHEDULE_WEEKDAYS = "specific_weekdays"
SCHEDULE_WEEKLY = "once_per_week"
SCHEDULE_CYCLE = "cycle"

SCHEDULE_TYPES = {
    SCHEDULE_DAILY,
    SCHEDULE_TIMES_PER_DAY,
    SCHEDULE_WEEKDAYS,
    SCHEDULE_WEEKLY,
    SCHEDULE_CYCLE,
}

STATUS_REQUIRED_NOW = "Required Now"
STATUS_NEXT_DOSE_DUE = "Next dose due"
STATUS_TAKEN = "Taken"
STATUS_SKIPPED = "Skipped"
STATUS_MISSED = "Missed"
STATUS_NOT_REQUIRED_TODAY = "Not Required Today"
STATUS_UNKNOWN = "Unknown"

# Backward-compatible aliases for older internal imports.
STATUS_DUE_NOW = STATUS_REQUIRED_NOW
STATUS_TAKE_LATER_TODAY = STATUS_NEXT_DOSE_DUE
STATUS_TAKEN_TODAY = STATUS_TAKEN
STATUS_SKIPPED_TODAY = STATUS_SKIPPED
STATUS_PARTIALLY_TAKEN = STATUS_NEXT_DOSE_DUE

DOSE_STATUS_TAKEN = "taken"
DOSE_STATUS_SKIPPED = "skipped"
DOSE_STATUS_MISSED = "missed"
DOSE_STATUS_PENDING = "pending"

DOSE_STATUSES = {
    DOSE_STATUS_TAKEN,
    DOSE_STATUS_SKIPPED,
    DOSE_STATUS_MISSED,
    DOSE_STATUS_PENDING,
}

EVENT_DUE = f"{DOMAIN}_due"
EVENT_MISSED = f"{DOMAIN}_missed"
EVENT_TAKEN = f"{DOMAIN}_taken"
EVENT_SKIPPED = f"{DOMAIN}_skipped"
EVENT_REQUIRED_TODAY = f"{DOMAIN}_required_today"
EVENT_NOT_REQUIRED_TODAY = f"{DOMAIN}_not_required_today"

EVENT_TYPES = {
    "due": EVENT_DUE,
    "missed": EVENT_MISSED,
    "taken": EVENT_TAKEN,
    "skipped": EVENT_SKIPPED,
    "required_today": EVENT_REQUIRED_TODAY,
    "not_required_today": EVENT_NOT_REQUIRED_TODAY,
}

TRIGGER_TYPES = tuple(EVENT_TYPES)

ACTION_MARK_TAKEN = "mark_taken"
ACTION_SKIP_DOSE = "skip_dose"
ACTION_MARK_NOT_TAKEN = "mark_not_taken"

ACTION_TYPES = {ACTION_MARK_TAKEN, ACTION_SKIP_DOSE, ACTION_MARK_NOT_TAKEN}
