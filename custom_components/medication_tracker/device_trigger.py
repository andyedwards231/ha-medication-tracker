"""Device triggers for Medication Tracker."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo

from .const import DOMAIN, EVENT_TYPES, TRIGGER_TYPES

TRIGGER_SCHEMA = cv.DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Return a list of triggers supported by a medication device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        return []

    medication_ids = [
        identifier[1]
        for identifier in device.identifiers
        if len(identifier) == 2 and identifier[0] == DOMAIN
    ]
    if not medication_ids:
        return []

    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: trigger_type,
        }
        for trigger_type in TRIGGER_TYPES
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: dict,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a medication device trigger to the matching integration event."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(config[CONF_DEVICE_ID])
    medication_id = None
    if device is not None:
        for identifier in device.identifiers:
            if len(identifier) == 2 and identifier[0] == DOMAIN:
                medication_id = identifier[1]
                break

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_TYPES[config[CONF_TYPE]],
            event_trigger.CONF_EVENT_DATA: {"medication_id": medication_id},
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
