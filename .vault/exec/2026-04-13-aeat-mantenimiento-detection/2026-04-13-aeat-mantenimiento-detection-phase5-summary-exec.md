---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase5 summary - workflow pause-and-alert

Phase 5 grew `WorkflowAbortReason` with `SITE_UNAVAILABLE`,
attached an optional typed `SiteHealthAlert` field to
`WorkflowStep`, and added a typed `except SiteHealthError` arm to
every stage method in `aeat.application.workflow._engine` strictly before the
generic `except Exception`. The helper
`_record_site_unavailable` composes a `SiteHealthAlert` carrying
the current run identifier, appends a failed `WorkflowStep`, and
raises `_AbortError(reason=SITE_UNAVAILABLE)`. Run identifiers
are now computed provisionally at the top of `_drive` so an alert
raised before the deadline stage completes still carries a stable
hash. The existing test for
`test_models.TestWorkflowAbortReasons.test_exact_nine_reasons` was
updated to include the new value.

Steps: 5-1, 5-2, 5-3. New engine test proves the typed arm fires
before the generic exception arm and the `run_id` carried on the
alert matches `WorkflowResult.run_id`.
