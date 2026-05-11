"""Device actions for Medication Tracker."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import (
    ACTION_MARK_TAKEN,
    ACTION_TYPES,
    CONF_MEDICATION_ID,
    CONF_NOTE,
    CONF_SOURCE,
    DOMAIN,
)

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Optional(CONF_SOURCE): cv.string,
        vol.Optional(CONF_NOTE): cv.string,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Return a list of actions supported by a medication device."""
    medication_id = _medication_id_for_device(hass, device_id)
    if medication_id is None:
        return []

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: ACTION_MARK_TAKEN,
        }
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: dict,
    variables: dict,
    context: Context | None,
) -> None:
    """Execute a medication device action."""
    medication_id = _medication_id_for_device(hass, config[CONF_DEVICE_ID])
    if medication_id is None:
        raise HomeAssistantError("Medication device not found")

    if config[CONF_TYPE] != ACTION_MARK_TAKEN:
        raise HomeAssistantError(f"Unsupported medication action: {config[CONF_TYPE]}")

    service_data = {
        CONF_MEDICATION_ID: medication_id,
        CONF_SOURCE: config.get(CONF_SOURCE, "Automation"),
    }
    if note := config.get(CONF_NOTE):
        service_data[CONF_NOTE] = note

    await hass.services.async_call(
        DOMAIN,
        ACTION_MARK_TAKEN,
        service_data,
        blocking=True,
        context=context,
    )


def _medication_id_for_device(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the medication id for a device registry id."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return None
    for identifier in device.identifiers:
        if len(identifier) == 2 and identifier[0] == DOMAIN:
            return identifier[1]
    return None
