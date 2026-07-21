---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-03'
modified: '2026-07-08'
step_id: 'S254'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`, `aeat.core.time`

## Scope

- `src/aeat/application/review/_models.py`

## Description

Rewired the three cross-package private import names in `src/aeat/application/review/_models.py` onto their owning packages' promoted top-level facades, per the import-centralization ADR Ruling 1.

- Routed `validate_utc_aware` off the private `core.time._utc` submodule onto the `aeat.core.time` public facade.
- Routed `WorkflowEvent` off the private `workflow._models` submodule; it now imports from the shared intra-package leaf `aeat.application._workflow_review_models`.
- Routed `utc_now` off the private `workflow._utils` submodule; it now imports from the same shared leaf module.

## Outcome

The module resolves `validate_utc_aware` through the `core.time` facade and both workflow-owned runtime names through the shared intra-package leaf, so no cross-package private submodule import remains. Landed in commit `3c1748da78` (facade routing) and finalised by commit `5557004b8d` (review<->workflow cycle break via the shared leaf). Verified `python -c "import aeat.application.review._models, aeat.application.review"` succeeds and `dev/import_hygiene_scan.py` reports zero production Family-1 violations. Behavior-preserving: no symbol relocation, no signature change.

## Notes

The rewrite code was authored and committed in the batched facade-routing landing (`3c1748da78`) plus the follow-on cycle-break (`5557004b8d`); the checkbox for this Step is closed here against those commit SHAs as the durable evidence trail, matching this Wave's exec-record-anchors-commit convention.
