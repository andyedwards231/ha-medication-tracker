# Medication Tracker

A local Home Assistant integration for tracking medication schedules and dose history.

## Install With HACS

1. Open HACS.
2. Go to **Integrations**.
3. Add this custom repository:

   ```text
   https://github.com/andyedwards231/ha-medication-tracker
   ```

4. Choose category **Integration**.
5. Install **Medication Tracker**.
6. Restart Home Assistant.
7. Go to **Settings > Devices & services > Add integration**.
8. Search for **Medication Tracker**.

## Add Medications

The first setup creates your first medication. To add another medication, run the **Add integration** flow again or use the integration options.

Each medication is created as a Home Assistant device with:

- a main status sensor
- a **Needs attention** binary sensor
- diagnostic sensors for schedule and dose details
- buttons for **Mark taken**, **Skip dose**, and **Mark not taken**

## Updating

Update through HACS, then restart Home Assistant.

## Documentation

Full instructions are in [custom_components/medication_tracker/README.md](custom_components/medication_tracker/README.md).
