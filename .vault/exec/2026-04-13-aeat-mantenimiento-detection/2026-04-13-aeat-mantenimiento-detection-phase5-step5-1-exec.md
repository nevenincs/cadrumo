---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase5-step5-1 extend abort enum and step record

## Intent

Grow the workflow abort enum and attach an optional typed
site-health alert to `WorkflowStep`.

## Changes

- `src/aeat/application/workflow/_models.py`:
  - Added `WorkflowAbortReason.SITE_UNAVAILABLE` strictly before
    `UNHANDLED_EXCEPTION`.
  - Added `WorkflowStep.site_health_alert: SiteHealthAlert | None`
    via a forward reference + `TYPE_CHECKING` import.
- `src/aeat/application/workflow/__init__.py` — imports `SiteHealthAlert` at the
  subpackage boundary (safe site), assigns it into `_models` module
  globals, and calls `WorkflowStep.model_rebuild()` so the forward
  reference resolves. This preserves the circular-import break
  described in Step 1.2's exec record.

## Deviations

- Plan said `extra="forbid"` must reject unknown keys; optional
  missing field is already permitted by default. Added a light
  comment in the code isn't necessary — pydantic v2 handles this
  by default.
