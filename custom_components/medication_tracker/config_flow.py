"""Config flow for Medication Tracker."""

from __future__ import annotations

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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create the local Medication Tracker entry."""
        await self.async_set_unique_id("local")
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            medication = _normalize_flow_input(user_input)
            if not medication[CONF_DUE_TIMES]:
                errors[CONF_DUE_TIMES] = "invalid_time"
            elif (
                medication[CONF_SCHEDULE_TYPE] == SCHEDULE_CYCLE
                and (
                    not medication.get(CONF_CYCLE_START_DATE)
                    or not medication.get(CONF_CYCLE_ON_DAYS)
                )
            ):
                errors["base"] = "cycle_required"
            else:
                return self.async_create_entry(
                    title="Medication Tracker",
                    data={"initial_medication": medication},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_medication_schema(),
            errors=errors,
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return MedicationTrackerOptionsFlow()


class MedicationTrackerOptionsFlow(config_entries.OptionsFlow):
    """Allow adding more medications from the options UI."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options form."""
        errors: dict[str, str] = {}
        if user_input is not None:
            medication = _normalize_flow_input(user_input)
            if not medication[CONF_DUE_TIMES]:
                errors[CONF_DUE_TIMES] = "invalid_time"
            else:
                options = dict(self.config_entry.options)
                pending = list(options.get("pending_medications", []))
                pending.append(medication)
                options["pending_medications"] = pending
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_medication_schema(),
            errors=errors,
            description_placeholders={
                "services": "Use service actions for editing or removing existing medications."
            },
        )


def _medication_schema() -> vol.Schema:
    """Return the medication form schema."""
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
            vol.Optional(CONF_NOTES): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
            ),
            vol.Optional(CONF_WEEKDAYS): SelectSelector(
                SelectSelectorConfig(
                    options=WEEKDAY_OPTIONS,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(CONF_CYCLE_START_DATE): DateSelector(),
            vol.Optional(CONF_CYCLE_ON_DAYS): NumberSelector(
                NumberSelectorConfig(min=1, max=365, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_CYCLE_OFF_DAYS): NumberSelector(
                NumberSelectorConfig(min=0, max=365, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_GRACE_PERIOD_MINUTES, default=DEFAULT_GRACE_PERIOD_MINUTES
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=1440, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_ICON): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
        }
    )


def _normalize_flow_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form data to service-compatible data."""
    due_times = [
        part.strip()
        for part in str(user_input.get(CONF_DUE_TIMES, "")).split(",")
        if part.strip()
    ]
    return {
        CONF_NAME: user_input[CONF_NAME],
        CONF_DOSE: user_input[CONF_DOSE],
        CONF_SCHEDULE_TYPE: user_input[CONF_SCHEDULE_TYPE],
        CONF_DUE_TIMES: due_times,
        CONF_NOTES: user_input.get(CONF_NOTES),
        CONF_WEEKDAYS: [int(day) for day in user_input.get(CONF_WEEKDAYS, [])],
        CONF_CYCLE_START_DATE: user_input.get(CONF_CYCLE_START_DATE),
        CONF_CYCLE_ON_DAYS: user_input.get(CONF_CYCLE_ON_DAYS),
        CONF_CYCLE_OFF_DAYS: user_input.get(CONF_CYCLE_OFF_DAYS),
        CONF_GRACE_PERIOD_MINUTES: int(
            user_input.get(CONF_GRACE_PERIOD_MINUTES, DEFAULT_GRACE_PERIOD_MINUTES)
        ),
        CONF_ICON: user_input.get(CONF_ICON),
    }
