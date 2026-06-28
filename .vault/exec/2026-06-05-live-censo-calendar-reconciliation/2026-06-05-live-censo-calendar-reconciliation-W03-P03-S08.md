---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S08'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W03.P03.S08 - live-backed calendar filing and message evidence

## Description

- Verified persisted live expedientes and notification snapshot facades.
- Ran calendar aggregation over 2026 to confirm live-backed message events render.
- Ran calendar aggregation over 2024 to confirm live-backed filing events and justificante state render when the event dates fall in range.
- Ran focused overview, censo, live CLI, modelo verification, and lint gates.

## Outcome

- `app live expedientes latest` returned snapshot `5eea370b25ecf6d3e562dcbc0c08807d0381f34d72447b4a84fde4ec9570eb3e`, captured `2026-06-05T18:00:52.070388+00:00`, with six declaration rows for Modelo 303 in 2024.
- `app live notifications latest` returned snapshot `a26f25109235179fab0e86994efa569b3552b20904f6d99b0e3794f4f1c95e8e`, captured `2026-06-05T18:01:36.394997+00:00`, with one notification row.
- `app overview calendar --from 2026-01-01 --to 2026-12-31 --all-profiles --allow-incomplete` rendered the notification as a `message` event for `2026-06-03`.
- `app overview calendar --from 2024-01-01 --to 2024-12-31 --all-profiles --allow-incomplete` rendered live-backed Modelo 303 filing events for periods `1T` and `2T`; both carried `aeat_submission_state = justificante_verified` and `justificante_verified = true`.
- The calendar did not emit legal obligation entries for any profile because every inspected profile still had `taxpayer_model_declared = false`.

## Notes

- This step verifies evidence projection from persisted live snapshots, not legal obligation enrolment. Steps `S06` and `S07` remain open for censo-backed taxpayer-model reconciliation and real filing-date obligation rows.
- Focused gates passed: censo/profile tests `16 passed`; overview calendar tests `63 passed`; live CLI surface tests `78 passed`; modelo verification regression tests `7 passed`; ruff passed on the touched censo, calendar, and modelo files.
