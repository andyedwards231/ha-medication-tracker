# Medication Tracker

Medication Tracker is a local Home Assistant integration for medication schedules and dose history.

## Install

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

## Update

Update through HACS, then restart Home Assistant.

If Home Assistant still shows old wording or old entities after updating, restart Home Assistant and refresh the browser.

## Add Medications

To add the first medication:

1. Go to **Settings > Devices & services**.
2. Choose **Add integration**.
3. Search for **Medication Tracker**.
4. Choose the schedule type.
5. Fill in the medication details.

To add another medication, run the same add flow again. The integration keeps one Medication Tracker entry and adds another medication device.

You can also add a medication from the integration options or with the `medication_tracker.add_medication` action.

## Schedule Types

- `every_day`: Required every day.
- `multiple_times_per_day`: Required every day, once for each due time.
- `specific_weekdays`: Required only on selected weekdays.
- `once_per_week`: Required on one selected weekday each week.
- `cycle`: Repeats active and rest days.

In service calls, weekdays use numbers: Monday is `0`, Sunday is `6`.

For cycle schedules:

- `cycle_start_date`: First active day.
- `cycle_on_days`: Number of active days.
- `cycle_off_days`: Number of rest days.

Example: 21 active days and 7 rest days repeats every 28 days.

## Medication Device

Each medication is a Home Assistant device.

The device includes:

- main status sensor
- **Needs attention** binary sensor
- diagnostic sensors for schedule and dose details
- **Mark taken** button
- **Skip dose** button
- **Mark not taken** button

The main status sensor can show values such as:

- `Missed at 08:00`
- `Due now (13:00)`
- `Take later today at 20:00`
- `Taken at 10:05`
- `Taken at 10:05, next at 20:00`
- `Taken at 10:05, next dose tomorrow`
- `Skipped at 10:05, next dose tomorrow`
- `Not required today`

Use the `base_status` diagnostic sensor if you need a stable value for automations.

## Buttons

- **Mark taken** marks the next due, missed, or pending dose as taken.
- **Skip dose** marks the next due, missed, or pending dose as skipped.
- **Mark not taken** removes the latest taken record.

## Service Actions

Use the medication's main sensor as the target.

Mark the next dose as taken:

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
  reason: Not needed today
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

## Examples

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

Medication Tracker fires these events:

- `medication_tracker_due`
- `medication_tracker_missed`
- `medication_tracker_taken`
- `medication_tracker_skipped`
- `medication_tracker_required_today`
- `medication_tracker_not_required_today`

Event data includes the medication name, dose, entity id, medication id, scheduled time, next due time, schedule type, source, and note where available.

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

## Device Automations

Medication devices expose automation triggers for due, missed, taken, skipped, required today, and not required today.

They also expose actions for mark taken, skip dose, and mark not taken.

## Dashboard Example

This example uses only built-in Lovelace cards. Replace the three medication
sensor entities and button entities with your own.

Remove any row or button group you do not need.

```yaml
type: vertical-stack
cards:
  - type: markdown
    title: Medication
    content: |
      {% set entities = expand(
        'sensor.vitamin_d',
        'sensor.inhaler',
        'sensor.antibiotic'
      ) %}
      | | Medication | Status | Today |
      |---|---|---|---|
      {% for med in entities if med.state not in ['unknown', 'unavailable'] %}
      {% set status = med.attributes.base_status %}
      {% set icon =
        '⚠️' if status == 'Missed' else
        '💊' if status == 'Due now' else
        '✅' if status == 'Taken today' else
        '⏭️' if status == 'Skipped today' else
        '◐' if status == 'Partially taken' else
        '🕒' if status == 'Take later today' else
        '−' if status == 'Not required today' else
        '?' %}
      {% set taken = med.attributes.doses_taken_today | default(0) %}
      {% set due = med.attributes.doses_due_today | default(0) %}
      {% set missed = med.attributes.missed_doses_today | default(0) %}
      {% set skipped = med.attributes.skipped_doses_today | default(0) %}
      {% set next_due = med.attributes.next_due %}
      | {{ icon }} | **{{ med.attributes.medication_name or med.name }}**<br>{{ med.attributes.dose or '' }} | {{ med.state }}{% if next_due %}<br>Next: {{ as_timestamp(next_due) | timestamp_custom('%H:%M', true) }}{% endif %} | {{ taken }}/{{ due }}{% if missed | int > 0 %}<br>Missed: {{ missed }}{% endif %}{% if skipped | int > 0 %}<br>Skipped: {{ skipped }}{% endif %} |
      {% endfor %}

  - type: grid
    columns: 3
    square: false
    cards:
      - type: button
        entity: button.vitamin_d_mark_taken
        name: Vitamin D
        icon: mdi:check
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.vitamin_d_mark_taken
      - type: button
        entity: button.vitamin_d_skip_dose
        name: Skip
        icon: mdi:skip-next
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.vitamin_d_skip_dose
      - type: button
        entity: button.vitamin_d_mark_not_taken
        name: Undo
        icon: mdi:undo
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.vitamin_d_mark_not_taken

      - type: button
        entity: button.inhaler_mark_taken
        name: Inhaler
        icon: mdi:check
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.inhaler_mark_taken
      - type: button
        entity: button.inhaler_skip_dose
        name: Skip
        icon: mdi:skip-next
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.inhaler_skip_dose
      - type: button
        entity: button.inhaler_mark_not_taken
        name: Undo
        icon: mdi:undo
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.inhaler_mark_not_taken

      - type: button
        entity: button.antibiotic_mark_taken
        name: Antibiotic
        icon: mdi:check
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.antibiotic_mark_taken
      - type: button
        entity: button.antibiotic_skip_dose
        name: Skip
        icon: mdi:skip-next
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.antibiotic_skip_dose
      - type: button
        entity: button.antibiotic_mark_not_taken
        name: Undo
        icon: mdi:undo
        show_state: false
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.antibiotic_mark_not_taken
```

The status table uses each medication's main sensor. The buttons use the
medication button entities created by the integration.

## Storage

Medication definitions and dose history are stored locally. Dose history is kept for 90 days by default.

Each dose event stores:

- medication id
- scheduled datetime
- status: `pending`, `taken`, `skipped`, or `missed`
- action datetime, where relevant
- source, where relevant
- note or reason, where relevant

## Troubleshooting

- Update through HACS, then restart Home Assistant.
- If HACS does not show the latest version, reload HACS or wait for the next refresh.
- If old wording still appears after updating, restart Home Assistant and refresh the browser.
- If you cannot add another medication, make sure you are on the latest version and run the add flow again.
- If a button works but the screen looks stale, refresh the browser and check the main status sensor.
