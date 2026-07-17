---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S252'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.application.workflow`

## Scope

- `src/aeat/application/review/_actions.py`

## Description

Rewired the three cross-package private import names in `src/aeat/application/review/_actions.py` that reached into the sibling `aeat.application.workflow` package's private submodules, per the import-centralization ADR Ruling 1.

- Routed `WorkflowEvent` off the private `workflow._models` submodule; it now imports from the shared intra-package leaf `aeat.application._workflow_review_models`, which jointly owns `WorkflowEvent` with the review/ledger records to resolve the review<->workflow mutual runtime dependency.
- Routed `utc_now` off the private `workflow._utils` submodule; it is now re-exported from the same shared leaf module and imported intra-package.
- Routed `WorkflowState` off the private `workflow._models` submodule onto the `aeat.application.workflow` public facade (under `TYPE_CHECKING`, the only place this module references the type).

## Outcome

The module no longer imports from any `aeat.application.workflow` private submodule; the two runtime names come from the shared intra-package leaf and the type-only `WorkflowState` from the workflow facade. Landed in commit `3c1748da78` (facade routing) and finalised by commit `5557004b8d` (review<->workflow cycle break via the shared leaf, which removed the transitional documented submodule-import exception). Verified `python -c "import aeat.application.review._actions, aeat.application.review"` succeeds and `dev/import_hygiene_scan.py` reports zero production Family-1 violations. Behavior-preserving: no signature change.

## Notes

The rewrite code was authored and committed in the batched facade-routing landing (`3c1748da78`) plus the follow-on cycle-break (`5557004b8d`); the checkbox for this Step is closed here against those commit SHAs as the durable evidence trail, matching this Wave's exec-record-anchors-commit convention.
