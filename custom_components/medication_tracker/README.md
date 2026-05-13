# Medication Tracker

Local-only Home Assistant custom integration for tracking medication schedules, reminders, action buttons, and dose history.

## Installation

### HACS

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

### Manual

Copy this folder to:

```text
<config>/custom_components/medication_tracker
```

Restart Home Assistant, then add the integration from **Settings > Devices & services**.

## Updating

Update through HACS, then restart Home Assistant. If the UI still shows old wording or old entities after updating, restart Home Assistant again and reload the browser. Home Assistant caches integration metadata during startup.

## Adding Medications

Medication Tracker keeps one integration entry and creates one Home Assistant device per medication.

To add the first medication:

1. Go to **Settings > Devices & services**.
2. Choose **Add integration**.
3. Search for **Medication Tracker**.
4. Choose the schedule type.
5. Fill in the medication details.

To add more medications, run the same add flow again. If Medication Tracker is already configured, the flow adds the new medication to the existing integration and creates another medication device.

You can also add a medication from the integration options or by calling `medication_tracker.add_medication`.

## Schedule Types

- `every_day`: Required every calendar day at the due time or times.
- `multiple_times_per_day`: Required every day, with one dose for each due time.
- `specific_weekdays`: Required only on selected weekdays.
- `once_per_week`: Required on one selected weekday each week.
- `cycle`: Repeats active and rest blocks.

Weekdays use Python weekday numbers in service calls: Monday is `0`, Sunday is `6`.

Cycle schedules use:

- `cycle_start_date`: First active day of the cycle.
- `cycle_on_days`: Number of active days when doses are required.
- `cycle_off_days`: Number of rest days when doses are not required.

Example: `21` active days and `7` rest days repeats a 28-day pattern.

## Medication Devices

Each medication is a Home Assistant device. The device page includes:

- Main status sensor.
- **Needs attention** binary sensor.
- Diagnostic sensors for schedule and dose data.
- Button entities for quick actions.

### Main Status

The main sensor is dynamic. Example states:

- `Missed at 08:00`
- `Due now (13:00)`
- `Take later today at 20:00`
- `Taken at 10:05`
- `Taken at 10:05, next at 20:00`
- `Not required today`

The stable simple status is exposed as `base_status` for dashboards and automations.

### Diagnostic Sensors And Attributes

The main medication data is available both as sensor attributes and as separate diagnostic sensors on the medication device:

- `medication_name`
- `base_status`
- `display_status`
- `dose`
- `schedule_type`
- `due_times`
- `next_due`
- `last_taken`
- `taken_today`
- `required_today`
- `doses_due_today`
- `doses_taken_today`
- `remaining_doses_today`
- `missed_doses_today`
- `skipped_doses_today`
- `cycle_day`, for cycle schedules
- `cycle_status`, for cycle schedules
- `grace_period_minutes`
- `notes`

### Button Entities

Each medication device includes:

- **Mark taken**: Marks the next relevant due, missed, or pending dose as taken.
- **Skip dose**: Marks the next relevant due, missed, or pending dose as intentionally skipped.
- **Mark not taken**: Undoes the latest taken record for that medication.

These buttons use the same local service actions and event flow as automations.

## Service Actions

Use the medication's main sensor as the target where possible.

Mark the next relevant dose as taken:

```yaml
action: medication_tracker.mark_taken
target:
  entity_id: sensor.vitamin_d
data:
  source: Dashboard
  note: Taken with breakfast
```

Mark a specific scheduled dose as taken:

```yaml
action: medication_tracker.mark_taken
target:
  entity_id: sensor.inhaler
data:
  scheduled_for: "2026-05-13T13:00:00+01:00"
  taken_at: "2026-05-13T13:05:00+01:00"
  source: Automation
```

Undo the latest taken dose:

```yaml
action: medication_tracker.undo_taken
target:
  entity_id: sensor.vitamin_d
```

Skip a dose:

```yaml
action: medication_tracker.skip_dose
target:
  entity_id: sensor.vitamin_d
data:
  reason: Doctor advised skipping today
  source: Dashboard
```

Add a medication:

```yaml
action: medication_tracker.add_medication
data:
  name: Vitamin D
  dose: 1 tablet
  schedule_type: every_day
  due_times:
    - "08:00"
```

Update a medication:

```yaml
action: medication_tracker.update_medication
target:
  entity_id: sensor.vitamin_d
data:
  dose: 2 tablets
  due_times:
    - "09:00"
  grace_period_minutes: 90
```

Remove a medication:

```yaml
action: medication_tracker.remove_medication
target:
  entity_id: sensor.vitamin_d
```

## Schedule Examples

Daily at 08:00:

```yaml
action: medication_tracker.add_medication
data:
  name: Vitamin D
  dose: 1 tablet
  schedule_type: every_day
  due_times:
    - "08:00"
```

Three times per day:

```yaml
action: medication_tracker.add_medication
data:
  name: Inhaler
  dose: 2 puffs
  schedule_type: multiple_times_per_day
  due_times:
    - "08:00"
    - "13:00"
    - "20:00"
```

Weekly on Monday:

```yaml
action: medication_tracker.add_medication
data:
  name: Weekly tablet
  dose: 10mg
  schedule_type: once_per_week
  weekdays:
    - 0
  due_times:
    - "09:00"
```

21 days on, 7 days off:

```yaml
action: medication_tracker.add_medication
data:
  name: Cycle medication
  dose: 1 tablet
  schedule_type: cycle
  cycle_start_date: "2026-05-13"
  cycle_on_days: 21
  cycle_off_days: 7
  due_times:
    - "08:00"
```

## Events

Medication Tracker fires normal Home Assistant events:

- `medication_tracker_due`
- `medication_tracker_missed`
- `medication_tracker_taken`
- `medication_tracker_skipped`
- `medication_tracker_required_today`
- `medication_tracker_not_required_today`

Event data includes:

- `entity_id`
- `medication_id`
- `medication_name`
- `dose`
- `scheduled_for`
- `due_time`
- `next_due`
- `schedule_type`
- `cycle_day`, for cycle schedules
- `cycle_status`, for cycle schedules
- `source`, where relevant
- `note`, where relevant

`due`, `missed`, `required_today`, and `not_required_today` events are de-duplicated so they do not fire repeatedly for the same dose or day.

## Automation Examples

Medication due reminder:

```yaml
alias: Medication due reminder
triggers:
  - trigger: event
    event_type: medication_tracker_due
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "Medication due"
      message: "{{ trigger.event.data.medication_name }} is due now: {{ trigger.event.data.dose }}"
```

Medication missed reminder:

```yaml
alias: Medication missed reminder
triggers:
  - trigger: event
    event_type: medication_tracker_missed
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "Medication missed"
      message: "{{ trigger.event.data.medication_name }} was due at {{ trigger.event.data.due_time }}"
```

Mark a medication as taken from an automation:

```yaml
actions:
  - action: medication_tracker.mark_taken
    target:
      entity_id: sensor.vitamin_d
    data:
      source: Automation
```

## Device Automations

Medication devices expose UI-friendly triggers:

- Medication becomes due
- Medication is missed
- Medication is marked as taken
- Medication is skipped
- Medication is required today
- Medication is not required today

Medication devices also expose UI-friendly actions:

- Mark medication as taken
- Skip medication dose
- Mark medication as not taken

These are backed by the normal events and service actions above.

## Lovelace Markdown Card

```yaml
type: markdown
content: |
  {% set meds = states.sensor
    | selectattr('attributes.medication_name', 'defined')
    | selectattr('attributes.base_status', 'defined')
    | list %}

  {% for med in meds %}
  ## {{ med.attributes.medication_name }}
  **Status:** {{ med.state }}
  **Dose:** {{ med.attributes.dose }}
  **Next due:** {{ med.attributes.next_due or 'None today' }}
  **Taken today:** {{ med.attributes.doses_taken_today }}/{{ med.attributes.doses_due_today }}
  **Missed:** {{ med.attributes.missed_doses_today }}

  {% endfor %}
```

## Storage And Retention

Medication definitions, individual dose events, skipped doses, missed doses, and taken timestamps are stored locally using Home Assistant storage helpers. The default history retention is 90 days. Older dose events and fired-event markers are cleaned up periodically during coordinator refreshes.

Dose events store:

- Medication ID
- Scheduled datetime
- Status: `pending`, `taken`, `skipped`, or `missed`
- Actual action datetime, where relevant
- Source, where relevant
- Note or reason, where relevant

## Troubleshooting

- If HACS does not show the latest version, reload HACS or wait for its next refresh, then restart Home Assistant after updating.
- If Home Assistant still says old wording such as **Add hub**, restart Home Assistant after updating. Manifest metadata is read at startup.
- If a button action changes history but the UI looks stale, refresh the browser and check the main status sensor plus the `base_status` diagnostic sensor.
- If you cannot add another medication, update to the latest version and restart. Running the add flow again should add another medication device to the existing integration.

## Time Handling

The integration uses Home Assistant timezone helpers and timezone-aware datetimes. Refreshes are scheduled when a dose becomes due, when a grace period expires, and at local midnight so daily required status is recalculated without frequent polling.
