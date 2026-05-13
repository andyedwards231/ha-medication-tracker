# Medication Tracker

Medication Tracker is a local-only Home Assistant custom integration for medication schedules, reminders, and dose history.

It creates one main sensor per medication, stores individual dose events locally, exposes service actions for marking doses taken or skipped, and fires Home Assistant events for due, missed, taken, skipped, required-today, and not-required-today changes.

## HACS Installation

1. Open HACS in Home Assistant.
2. Go to **Integrations**.
3. Open the three-dot menu and choose **Custom repositories**.
4. Add this repository URL:

   ```text
   https://github.com/andyedwards231/ha-medication-tracker
   ```

5. Select category **Integration**.
6. Install **Medication Tracker**.
7. Restart Home Assistant.
8. Go to **Settings > Devices & services > Add integration** and search for **Medication Tracker**.

## Manual Installation

Copy `custom_components/medication_tracker` into:

```text
<config>/custom_components/medication_tracker
```

Restart Home Assistant, then add the integration from **Settings > Devices & services**.

## Features

- Each medication appears as a Home Assistant device with dynamic status, diagnostic sensors, and action buttons.
- Local-only storage using Home Assistant storage helpers.
- No YAML setup, add-on, external app, or cloud API.
- Config flow support.
- Guided setup that only asks for weekday or cycle details when relevant.
- Multiple medications.
- Daily, multi-time daily, weekday, weekly, and cycle-based schedules.
- Individual dose event history with taken, skipped, missed, and pending states.
- 90-day default history retention.
- Event-based automation support.
- Device triggers, device actions, and button entities for UI-friendly automation setup.
- Local brand icon and logo for Home Assistant and HACS.

Full usage documentation is in [custom_components/medication_tracker/README.md](custom_components/medication_tracker/README.md).
