# Medication Tracker

Local-only Home Assistant custom integration for tracking medication schedules and dose history.

## Installation

1. Copy this folder to:

   ```text
   <config>/custom_components/medication_tracker
   ```

2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration**.
4. Search for **Medication Tracker**.
5. Create the first medication in the config flow.

No YAML setup, add-on, cloud API, or external app is required.

## Adding Medications

The config flow creates the first medication. It first asks which schedule type you want, then shows a second form tailored to that choice. For example, cycle start/on/off fields only appear after choosing **Cycle based**. Each medication is created as a Home Assistant device with its own status, diagnostic sensors, and action buttons. The options flow can add another medication. Service actions are the most flexible way to edit or remove existing medications.

### Schedule Types

- `every_day`
- `multiple_times_per_day`
- `specific_weekdays`
- `once_per_week`
- `cycle`

Weekdays use Python weekday numbers: Monday is `0`, Sunday is `6`.

Cycle schedules repeat active and rest blocks. A `cycle_start_date` is the first active day. `cycle_on_days` is the number of days when doses are required. `cycle_off_days` is the number of rest days when the medication is not required. For example, `21` active days and `7` rest days repeats a 28-day pattern.

### Examples

Daily at 08:00:

```yaml
service: medication_tracker.add_medication
data:
  name: Vitamin D
  dose: 1 tablet
  schedule_type: every_day
  due_times:
    - "08:00"
```

Three times per day:

```yaml
service: medication_tracker.add_medication
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
service: medication_tracker.add_medication
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
service: medication_tracker.add_medication
data:
  name: Cycle medication
  dose: 1 tablet
  schedule_type: cycle
  cycle_start_date: "2026-05-11"
  cycle_on_days: 21
  cycle_off_days: 7
  due_times:
    - "08:00"
```

## Service Actions

Mark the earliest unhandled due dose as taken:

```yaml
service: medication_tracker.mark_taken
target:
  entity_id: sensor.vitamin_d
data:
  source: Dashboard
  note: Taken with breakfast
```

Mark a specific scheduled dose as taken:

```yaml
service: medication_tracker.mark_taken
target:
  entity_id: sensor.inhaler
data:
  scheduled_for: "2026-05-11T13:00:00+01:00"
  taken_at: "2026-05-11T13:05:00+01:00"
  source: Automation
```

Undo the latest taken dose:

```yaml
service: medication_tracker.undo_taken
target:
  entity_id: sensor.vitamin_d
```

Skip a dose:

```yaml
service: medication_tracker.skip_dose
target:
  entity_id: sensor.vitamin_d
data:
  reason: Doctor advised skipping today
  source: Dashboard
```

Remove a medication:

```yaml
service: medication_tracker.remove_medication
target:
  entity_id: sensor.vitamin_d
```

Update a medication:

```yaml
service: medication_tracker.update_medication
target:
  entity_id: sensor.vitamin_d
data:
  dose: 2 tablets
  due_times:
    - "09:00"
  grace_period_minutes: 90
```

## Sensor States

- `Not required today`: The schedule does not require a dose today.
- `Missed`: At least one required dose passed its grace period.
- `Due now`: At least one unhandled dose is currently due.
- `Partially taken`: Some doses are handled and more remain today.
- `Take later today`: A dose is scheduled later today.
- `Taken today`: All of today's scheduled doses are handled.
- `Unknown`: The integration cannot determine a better status.

State priority is:

1. `Not required today`
2. `Missed`
3. `Due now`
4. `Partially taken`
5. `Take later today`
6. `Taken today`
7. `Unknown`

Skipped doses count as handled for the daily completion state, but are exposed separately in attributes.

## Attributes

Each medication sensor exposes:

- `medication_name`
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

The integration also creates a binary sensor per medication named **Needs attention**, which is on when the medication is due or missed. The main attributes are also exposed as separate diagnostic sensors on the medication device so they are easier to use in dashboards, automations, and the device page.

## Button Entities

Each medication device includes these button entities:

- **Mark taken**: marks the next relevant due or pending dose as taken.
- **Skip dose**: marks the next relevant dose as intentionally skipped.
- **Mark not taken**: undoes the latest taken record for that medication.

These buttons call the same local service actions as automations and dashboards, so dose history and events stay consistent.

## Events

The integration fires these Home Assistant events:

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

### Event Automation

```yaml
alias: Medication due reminder
trigger:
  - platform: event
    event_type: medication_tracker_due
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "Medication due"
      message: "{{ trigger.event.data.medication_name }} is due now: {{ trigger.event.data.dose }}"
```

Missed dose reminder:

```yaml
alias: Medication missed reminder
trigger:
  - platform: event
    event_type: medication_tracker_missed
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "Medication missed"
      message: "{{ trigger.event.data.medication_name }} was due at {{ trigger.event.data.due_time }}"
```

## Device Trigger Notes

Medication devices expose UI-friendly automation triggers:

- Medication becomes due
- Medication is missed
- Medication is marked as taken
- Medication is skipped
- Medication is required today
- Medication is not required today

These are backed by the normal Home Assistant events above. Event automations are still the most portable option.

Medication devices also expose a UI-friendly action:

- Mark medication as taken
- Skip medication dose
- Mark medication as not taken

These device actions call the matching Medication Tracker services for the selected medication. They are intended for simple automations where you want to choose the medication device in the visual editor.

## Lovelace Markdown Card

```yaml
type: markdown
content: |
  {% set meds = states.sensor
    | selectattr('attributes.medication_name', 'defined')
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

## Storage and Retention

Medication definitions, individual dose events, skipped doses, missed doses, and taken timestamps are stored locally using Home Assistant storage helpers. The default history retention is 90 days. Older dose events and fired-event markers are cleaned up periodically during coordinator refreshes.

Dose events store:

- Medication ID
- Scheduled datetime
- Status: `pending`, `taken`, `skipped`, or `missed`
- Actual action datetime, where relevant
- Source, where relevant
- Note or reason, where relevant

## Time Handling

The integration uses Home Assistant timezone helpers and timezone-aware datetimes. Refreshes are scheduled when a dose becomes due, when a grace period expires, and at local midnight so daily required status is recalculated without frequent polling.
