"""Config flow for Medication Tracker."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    DateSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CYCLE_OFF_DAYS,
    CONF_CYCLE_ON_DAYS,
    CONF_CYCLE_START_DATE,
    CONF_DOSE,
    CONF_DUE_TIMES,
    CONF_GRACE_PERIOD_MINUTES,
    CONF_ICON,
    CONF_NOTES,
    CONF_SCHEDULE_TYPE,
    CONF_WEEKDAYS,
    DEFAULT_GRACE_PERIOD_MINUTES,
    DOMAIN,
    SCHEDULE_CYCLE,
    SCHEDULE_DAILY,
    SCHEDULE_TIMES_PER_DAY,
    SCHEDULE_WEEKDAYS,
    SCHEDULE_WEEKLY,
)
from .schedule import normalize_due_times

WEEKDAY_OPTIONS = [
    {"value": "0", "label": "Monday"},
    {"value": "1", "label": "Tuesday"},
    {"value": "2", "label": "Wednesday"},
    {"value": "3", "label": "Thursday"},
    {"value": "4", "label": "Friday"},
    {"value": "5", "label": "Saturday"},
    {"value": "6", "label": "Sunday"},
]

SCHEDULE_OPTIONS = [
    {"value": SCHEDULE_DAILY, "label": "Every day"},
    {"value": SCHEDULE_TIMES_PER_DAY, "label": "Multiple times per day"},
    {"value": SCHEDULE_WEEKDAYS, "label": "Specific weekdays"},
    {"value": SCHEDULE_WEEKLY, "label": "Once per week"},
    {"value": SCHEDULE_CYCLE, "label": "Cycle based"},
]


class MedicationTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Medication Tracker config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._schedule_type = SCHEDULE_DAILY

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the local Medication Tracker setup."""
        return await self.async_step_schedule(user_input)

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose the schedule type before showing schedule-specific fields."""
        if user_input is not None:
            self._schedule_type = user_input[CONF_SCHEDULE_TYPE]
            return await self.async_step_medication()

        return self.async_show_form(
            step_id="schedule",
            data_schema=_schedule_type_schema(),
        )

    async def async_step_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect medication details for the selected schedule type."""
        errors: dict[str, str] = {}
        if user_input is not None:
            medication, errors = _normalize_medication_input(
                user_input, self._schedule_type
            )
            if not errors:
                if existing_entry := _existing_entry(self):
                    _queue_medication_for_entry(self.hass, existing_entry, medication)
                    return self.async_abort(reason="medication_added")
                return self.async_create_entry(
                    title="Medication Tracker",
                    data={"initial_medication": medication},
                )

        return self.async_show_form(
            step_id="medication",
            data_schema=_medication_schema(self._schedule_type),
            errors=errors,
            description_placeholders={
                "schedule_summary": _schedule_summary(self._schedule_type)
            },
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return MedicationTrackerOptionsFlow(config_entry)


class MedicationTrackerOptionsFlow(config_entries.OptionsFlow):
    """Allow adding more medications from the options UI."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize flow state."""
        self.config_entry = config_entry
        self._schedule_type = SCHEDULE_DAILY

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start adding another medication."""
        return await self.async_step_schedule(user_input)

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose the schedule type before showing schedule-specific fields."""
        if user_input is not None:
            self._schedule_type = user_input[CONF_SCHEDULE_TYPE]
            return await self.async_step_medication()

        return self.async_show_form(
            step_id="schedule",
            data_schema=_schedule_type_schema(),
        )

    async def async_step_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect medication details for the selected schedule type."""
        errors: dict[str, str] = {}
        if user_input is not None:
            medication, errors = _normalize_medication_input(
                user_input, self._schedule_type
            )
            if not errors:
                options = dict(self.config_entry.options)
                pending = list(options.get("pending_medications", []))
                pending.append(medication)
                options["pending_medications"] = pending
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="medication",
            data_schema=_medication_schema(self._schedule_type),
            errors=errors,
            description_placeholders={
                "schedule_summary": _schedule_summary(self._schedule_type),
                "services": "Existing medications can be edited or removed from service actions.",
            },
        )


def _schedule_type_schema() -> vol.Schema:
    """Return the first-step schedule type schema."""
    return vol.Schema(
        {
            vol.Required(CONF_SCHEDULE_TYPE, default=SCHEDULE_DAILY): SelectSelector(
                SelectSelectorConfig(
                    options=SCHEDULE_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _existing_entry(
    flow: config_entries.ConfigFlow,
) -> config_entries.ConfigEntry | None:
    """Return the existing Medication Tracker entry, if one exists."""
    entries = flow._async_current_entries()
    return entries[0] if entries else None


def _queue_medication_for_entry(
    hass, entry: config_entries.ConfigEntry, medication: dict[str, Any]
) -> None:
    """Queue a medication to be imported by the loaded config entry."""
    options = dict(entry.options)
    pending = list(options.get("pending_medications", []))
    pending.append(medication)
    options["pending_medications"] = pending
    hass.config_entries.async_update_entry(entry, options=options)


def _medication_schema(schedule_type: str) -> vol.Schema:
    """Return the medication form schema for a selected schedule type."""
    fields: dict = {
        vol.Required(CONF_NAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_DOSE): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_DUE_TIMES, default="08:00"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
    }

    if schedule_type in {SCHEDULE_WEEKDAYS, SCHEDULE_WEEKLY}:
        fields[vol.Required(CONF_WEEKDAYS)] = SelectSelector(
            SelectSelectorConfig(
                options=WEEKDAY_OPTIONS,
                multiple=schedule_type == SCHEDULE_WEEKDAYS,
                mode=SelectSelectorMode.LIST,
            )
        )

    if schedule_type == SCHEDULE_CYCLE:
        fields.update(
            {
                vol.Required(
                    CONF_CYCLE_START_DATE, default=date.today().isoformat()
                ): DateSelector(),
                vol.Required(CONF_CYCLE_ON_DAYS, default=21): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=365, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_CYCLE_OFF_DAYS, default=7): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=365, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

    fields.update(
        {
            vol.Optional(
                CONF_GRACE_PERIOD_MINUTES, default=DEFAULT_GRACE_PERIOD_MINUTES
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=1440, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_ICON): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Optional(CONF_NOTES): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
            ),
        }
    )
    return vol.Schema(fields)


def _normalize_medication_input(
    user_input: dict[str, Any], schedule_type: str
) -> tuple[dict[str, Any], dict[str, str]]:
    """Normalize medication form data to service-compatible data."""
    due_times = normalize_due_times(
        [
            part.strip()
            for part in str(user_input.get(CONF_DUE_TIMES, "")).split(",")
            if part.strip()
        ]
    )
    errors: dict[str, str] = {}
    if not due_times:
        errors[CONF_DUE_TIMES] = "invalid_time"

    weekdays: list[int] = []
    if schedule_type in {SCHEDULE_WEEKDAYS, SCHEDULE_WEEKLY}:
        weekdays = _normalize_weekdays(user_input.get(CONF_WEEKDAYS))
        if not weekdays:
            errors[CONF_WEEKDAYS] = "weekdays_required"
        elif schedule_type == SCHEDULE_WEEKLY and len(weekdays) != 1:
            errors[CONF_WEEKDAYS] = "one_weekday_required"

    cycle_start_date = None
    cycle_on_days = None
    cycle_off_days = None
    if schedule_type == SCHEDULE_CYCLE:
        cycle_start_date = user_input.get(CONF_CYCLE_START_DATE)
        cycle_on_days = int(user_input.get(CONF_CYCLE_ON_DAYS, 0))
        cycle_off_days = int(user_input.get(CONF_CYCLE_OFF_DAYS, 0))
        if not cycle_start_date:
            errors[CONF_CYCLE_START_DATE] = "required"
        if cycle_on_days < 1:
            errors[CONF_CYCLE_ON_DAYS] = "required"
        if cycle_off_days < 0:
            errors[CONF_CYCLE_OFF_DAYS] = "required"

    medication = {
        CONF_NAME: user_input[CONF_NAME],
        CONF_DOSE: user_input[CONF_DOSE],
        CONF_SCHEDULE_TYPE: schedule_type,
        CONF_DUE_TIMES: due_times,
        CONF_NOTES: user_input.get(CONF_NOTES),
        CONF_WEEKDAYS: weekdays,
        CONF_CYCLE_START_DATE: cycle_start_date,
        CONF_CYCLE_ON_DAYS: cycle_on_days,
        CONF_CYCLE_OFF_DAYS: cycle_off_days,
        CONF_GRACE_PERIOD_MINUTES: int(
            user_input.get(CONF_GRACE_PERIOD_MINUTES, DEFAULT_GRACE_PERIOD_MINUTES)
        ),
        CONF_ICON: user_input.get(CONF_ICON),
    }
    return medication, errors


def _normalize_weekdays(value: Any) -> list[int]:
    """Normalize selector weekday output."""
    if value is None:
        return []
    if isinstance(value, list):
        return [int(day) for day in value]
    return [int(value)]


def _schedule_summary(schedule_type: str) -> str:
    """Return a short explanation for a selected schedule type."""
    summaries = {
        SCHEDULE_DAILY: "Every day: this medication is required every calendar day at the due time or times you enter.",
        SCHEDULE_TIMES_PER_DAY: "Multiple times per day: this medication is required every day, with one dose for each due time.",
        SCHEDULE_WEEKDAYS: "Specific weekdays: this medication is required only on the weekdays you choose.",
        SCHEDULE_WEEKLY: "Once per week: this medication is required on one weekday each week.",
        SCHEDULE_CYCLE: "Cycle based: this medication repeats blocks of active days and rest days. For example, 21 days on and 7 days off means doses are required for 21 days from the first active day, then not required for 7 days, then the pattern repeats.",
    }
    return summaries.get(schedule_type, "")
