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
        self._medication_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the local Medication Tracker setup."""
        await self.async_set_unique_id("local")
        self._abort_if_unique_id_configured()
        return await self.async_step_medication(user_input)

    async def async_step_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect the common medication fields."""
        if user_input is not None:
            medication, errors = _normalize_common_input(user_input)
            if not errors:
                self._medication_data = medication
                schedule_type = medication[CONF_SCHEDULE_TYPE]
                if schedule_type in {SCHEDULE_WEEKDAYS, SCHEDULE_WEEKLY}:
                    return await self.async_step_weekdays()
                if schedule_type == SCHEDULE_CYCLE:
                    return await self.async_step_cycle()
                return self._create_config_entry(medication)
        else:
            errors = {}

        return self.async_show_form(
            step_id="medication",
            data_schema=_common_medication_schema(),
            errors=errors,
        )

    async def async_step_weekdays(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect weekday schedule details only when needed."""
        schedule_type = self._medication_data[CONF_SCHEDULE_TYPE]
        errors: dict[str, str] = {}
        if user_input is not None:
            weekdays = _normalize_weekdays(user_input.get(CONF_WEEKDAYS))
            if not weekdays:
                errors[CONF_WEEKDAYS] = "weekdays_required"
            elif schedule_type == SCHEDULE_WEEKLY and len(weekdays) != 1:
                errors[CONF_WEEKDAYS] = "one_weekday_required"
            else:
                self._medication_data[CONF_WEEKDAYS] = weekdays
                return self._create_config_entry(self._medication_data)

        return self.async_show_form(
            step_id="weekdays",
            data_schema=_weekday_schema(schedule_type),
            errors=errors,
        )

    async def async_step_cycle(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect cycle details only for cycle schedules."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_CYCLE_START_DATE):
                errors[CONF_CYCLE_START_DATE] = "required"
            elif int(user_input.get(CONF_CYCLE_ON_DAYS, 0)) < 1:
                errors[CONF_CYCLE_ON_DAYS] = "required"
            else:
                self._medication_data.update(
                    {
                        CONF_CYCLE_START_DATE: user_input.get(CONF_CYCLE_START_DATE),
                        CONF_CYCLE_ON_DAYS: int(user_input[CONF_CYCLE_ON_DAYS]),
                        CONF_CYCLE_OFF_DAYS: int(
                            user_input.get(CONF_CYCLE_OFF_DAYS, 0)
                        ),
                    }
                )
                return self._create_config_entry(self._medication_data)

        return self.async_show_form(
            step_id="cycle",
            data_schema=_cycle_schema(),
            errors=errors,
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return MedicationTrackerOptionsFlow(config_entry)

    def _create_config_entry(self, medication: dict[str, Any]) -> FlowResult:
        """Create the config entry with the first medication."""
        return self.async_create_entry(
            title="Medication Tracker",
            data={"initial_medication": medication},
        )


class MedicationTrackerOptionsFlow(config_entries.OptionsFlow):
    """Allow adding more medications from the options UI."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize flow state."""
        self.config_entry = config_entry
        self._medication_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start adding another medication."""
        return await self.async_step_medication(user_input)

    async def async_step_medication(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect common medication fields."""
        if user_input is not None:
            medication, errors = _normalize_common_input(user_input)
            if not errors:
                self._medication_data = medication
                schedule_type = medication[CONF_SCHEDULE_TYPE]
                if schedule_type in {SCHEDULE_WEEKDAYS, SCHEDULE_WEEKLY}:
                    return await self.async_step_weekdays()
                if schedule_type == SCHEDULE_CYCLE:
                    return await self.async_step_cycle()
                return self._create_options_entry(medication)
        else:
            errors = {}

        return self.async_show_form(
            step_id="medication",
            data_schema=_common_medication_schema(),
            errors=errors,
            description_placeholders={
                "services": "Existing medications can be edited or removed from service actions."
            },
        )

    async def async_step_weekdays(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect weekday schedule details."""
        schedule_type = self._medication_data[CONF_SCHEDULE_TYPE]
        errors: dict[str, str] = {}
        if user_input is not None:
            weekdays = _normalize_weekdays(user_input.get(CONF_WEEKDAYS))
            if not weekdays:
                errors[CONF_WEEKDAYS] = "weekdays_required"
            elif schedule_type == SCHEDULE_WEEKLY and len(weekdays) != 1:
                errors[CONF_WEEKDAYS] = "one_weekday_required"
            else:
                self._medication_data[CONF_WEEKDAYS] = weekdays
                return self._create_options_entry(self._medication_data)

        return self.async_show_form(
            step_id="weekdays",
            data_schema=_weekday_schema(schedule_type),
            errors=errors,
        )

    async def async_step_cycle(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect cycle details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_CYCLE_START_DATE):
                errors[CONF_CYCLE_START_DATE] = "required"
            elif int(user_input.get(CONF_CYCLE_ON_DAYS, 0)) < 1:
                errors[CONF_CYCLE_ON_DAYS] = "required"
            else:
                self._medication_data.update(
                    {
                        CONF_CYCLE_START_DATE: user_input.get(CONF_CYCLE_START_DATE),
                        CONF_CYCLE_ON_DAYS: int(user_input[CONF_CYCLE_ON_DAYS]),
                        CONF_CYCLE_OFF_DAYS: int(
                            user_input.get(CONF_CYCLE_OFF_DAYS, 0)
                        ),
                    }
                )
                return self._create_options_entry(self._medication_data)

        return self.async_show_form(
            step_id="cycle",
            data_schema=_cycle_schema(),
            errors=errors,
        )

    def _create_options_entry(self, medication: dict[str, Any]) -> FlowResult:
        """Queue a medication for import by the loaded config entry."""
        options = dict(self.config_entry.options)
        pending = list(options.get("pending_medications", []))
        pending.append(medication)
        options["pending_medications"] = pending
        return self.async_create_entry(title="", data=options)


def _common_medication_schema() -> vol.Schema:
    """Return the common medication form schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_DOSE): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_SCHEDULE_TYPE, default=SCHEDULE_DAILY): SelectSelector(
                SelectSelectorConfig(
                    options=SCHEDULE_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_DUE_TIMES, default="08:00"): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
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


def _weekday_schema(schedule_type: str) -> vol.Schema:
    """Return a weekday form schema for weekly schedules."""
    multiple = schedule_type == SCHEDULE_WEEKDAYS
    return vol.Schema(
        {
            vol.Required(CONF_WEEKDAYS): SelectSelector(
                SelectSelectorConfig(
                    options=WEEKDAY_OPTIONS,
                    multiple=multiple,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


def _cycle_schema() -> vol.Schema:
    """Return the cycle-only form schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_CYCLE_START_DATE, default=date.today().isoformat()
            ): DateSelector(),
            vol.Required(CONF_CYCLE_ON_DAYS, default=21): NumberSelector(
                NumberSelectorConfig(min=1, max=365, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_CYCLE_OFF_DAYS, default=7): NumberSelector(
                NumberSelectorConfig(min=0, max=365, mode=NumberSelectorMode.BOX)
            ),
        }
    )


def _normalize_common_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Normalize the common medication form data."""
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

    medication = {
        CONF_NAME: user_input[CONF_NAME],
        CONF_DOSE: user_input[CONF_DOSE],
        CONF_SCHEDULE_TYPE: user_input[CONF_SCHEDULE_TYPE],
        CONF_DUE_TIMES: due_times,
        CONF_NOTES: user_input.get(CONF_NOTES),
        CONF_WEEKDAYS: [],
        CONF_CYCLE_START_DATE: None,
        CONF_CYCLE_ON_DAYS: None,
        CONF_CYCLE_OFF_DAYS: None,
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
