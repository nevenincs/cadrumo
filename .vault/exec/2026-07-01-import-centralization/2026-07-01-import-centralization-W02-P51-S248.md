---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:86e7db346e1f9d337d05185c8b4b1cf5e6652dfe87642d31d3e6e918b59706a0'
step_id: 'S248'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.outbound.aeat.browser`, `aeat.application.auth`, `aeat.application.review`, `aeat.application.user_profile`

## Scope

- `src/aeat/application/workflow/_models.py`

## Description

Rewired the five cross-package private import names in `src/aeat/application/workflow/_models.py` onto their owning packages' promoted top-level facades, per the import-centralization ADR Ruling 1.

- Routed `SiteHealthStatus` from the `aeat.adapters.outbound.aeat.browser` facade instead of the private `browser._site_health` submodule.
- Routed `AuthState` from the `aeat.application.auth` facade instead of the private `auth._models` submodule.
- Routed `build_lifecycle_service` (function-local import) from the `aeat.application.user_profile` facade instead of the private `user_profile._orchestration` submodule.
- Routed `InvoiceReviewRecord` and `LedgerReviewRecord` off the private `review._models` submodule; the review/workflow mutual runtime dependency was resolved by moving both records plus `WorkflowEvent` into the shared intra-package leaf module `aeat.application._workflow_review_models`, so this consumer now imports them intra-package rather than reaching into the sibling `application.review` package's private submodule.

## Outcome

All five names now resolve through the owning package facade or the shared intra-package leaf. Landed in commit `3c1748da78` (facade routing across the auth/filing/overview/wizard/review/workflow application packages) and finalised by commit `5557004b8d` (review<->workflow cycle break via the shared `_workflow_review_models` leaf), which superseded the transitional documented cycle-break exceptions. Verified `python -c "import aeat.application.workflow._models, aeat.application.workflow"` succeeds and `dev/import_hygiene_scan.py` reports zero production Family-1 violations. Behavior-preserving: no symbol relocation of a public API, no signature change.

## Notes

The rewrite code was authored and committed in the batched auth/review/workflow facade-routing landing (`3c1748da78`) plus the follow-on cycle-break (`5557004b8d`); the checkbox for this Step is closed here against those commit SHAs as the durable evidence trail, matching this Wave's exec-record-anchors-commit convention. The shared-leaf resolution removed even the transitional `CYCLE-BREAK-RATIONALE-WORKFLOW-REVIEW` submodule-import exceptions that the first commit had documented, so no cross-package private import remains in this file.
