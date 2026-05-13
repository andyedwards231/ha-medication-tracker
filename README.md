# Medication Tracker

Medication Tracker is a local-only Home Assistant custom integration for medication schedules, reminders, dose history, and simple medication action buttons.

Each medication appears as its own Home Assistant device with a dynamic status sensor, diagnostic sensors, a problem binary sensor, and buttons to mark the next relevant dose as taken, skipped, or not taken.

## Install With HACS

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

## Updating

When a new version is published, update it in HACS, then restart Home Assistant. The restart matters because Home Assistant loads integration metadata and platforms at startup.

## Manual Installation

Copy `custom_components/medication_tracker` into:

```text
<config>/custom_components/medication_tracker
```

Restart Home Assistant, then add the integration from **Settings > Devices & services**.

## How It Works Now

- Add the first medication from **Add integration**.
- Add more medications by running the add flow again, or from the integration options.
- Medication Tracker keeps one integration entry, but creates one Home Assistant device per medication.
- Each medication device has status/count sensors and button entities.
- Dose history is stored locally using Home Assistant storage helpers.
- No YAML setup, add-on, external app, or cloud API is required.

## Device Entities

Each medication device includes:

- Main status sensor with states such as `Due now (08:00)` or `Taken at 10:05, next at 20:00`.
- **Needs attention** binary sensor, on when a dose is due or missed.
- Diagnostic sensors for dose, schedule type, due times, next due, last taken, counts, cycle status, and notes.
- Buttons: **Mark taken**, **Skip dose**, and **Mark not taken**.

Full usage documentation is in [custom_components/medication_tracker/README.md](custom_components/medication_tracker/README.md).
