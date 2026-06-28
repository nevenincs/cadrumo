---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-adr]]"
---

# phase1-step1-2 create site-health models

## Intent

Land the strict-frozen-forbid pydantic v2 records and the closed
`SiteHealthState` enum under `aeat.status._site_health`.

## Changes

- `src/aeat/status/_site_health.py` — new module defining
  `SiteHealthState` (StrEnum), private `_SiteHealthRecord` base,
  `SiteHealthEvidence`, `SiteHealthStatus`, and `SiteHealthAlert`.
  The module also exposes a module-level `_URL_ADAPTER` for parser
  call sites.

## Circular-import note

`SiteHealthAlert.stage` is typed `WorkflowStage`. The module imports
`WorkflowStage` directly from `aeat.application.workflow._models` (not
`aeat.application.workflow`) so the status subpackage does not trigger the
workflow `__init__`. `_models.py` has no runtime dependency on
`aeat.status`, so the cycle is broken at import time.

## Acceptance

- Each model instantiates from valid kwargs and rejects unknown
  keys — verified by `src/aeat/status/test_site_health.py` model
  shape tests.

## Deviations

None.
