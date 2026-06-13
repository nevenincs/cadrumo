---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase5-step5-2 workflow engine typed arm

## Intent

Teach `WorkflowEngine` to catch `SiteHealthError` in a typed arm
strictly before the generic `except Exception`, and to record a
typed `SiteHealthAlert` on the failed `WorkflowStep`.

## Changes

- `src/aeat/application/workflow/_engine.py`:
  - New imports: `SiteHealthError` from `aeat.core.errors`,
    `SiteHealthAlert` from `aeat.status`.
  - `WorkflowEngine.__init__` stores a `_current_run_id` field.
  - `_drive` computes a provisional `run_id` from the caller
    targets so alerts raised before the deadline stage completes
    still carry a stable identifier.
  - Every stage wrapping a component call with `_record_unhandled`
    now has a preceding `except SiteHealthError` arm that delegates
    to `_record_site_unavailable`.
  - New helper `_record_site_unavailable` builds a `SiteHealthAlert`
    carrying the run id, appends a failed `WorkflowStep`, and
    raises `_AbortError(reason=SITE_UNAVAILABLE)`.

## Deviations

The plan asks for the run_id to be "the current" run_id. Because
the final `run_id` previously was computed only at the end of
`_drive`, the implementation computes a provisional run_id at the
top of `_drive` (using the caller-supplied targets) and reuses it
for the alert. When the obligation ultimately resolves to the same
`(modelo, period)` pair, the provisional hash equals the final
`WorkflowResult.run_id`, which is the property the test asserts.
