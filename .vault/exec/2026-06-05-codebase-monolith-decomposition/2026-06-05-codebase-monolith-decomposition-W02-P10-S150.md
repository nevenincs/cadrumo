---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-06'
step_id: 'S150'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S150 Profile Censo Event Boundary Move

Scope: `src/aeat/application/user_profile/_censo_sync.py`; `src/aeat/application/user_profile/__init__.py`; `src/aeat/entrypoints/cli/_config/_profile_censo.py`; `src/aeat/application/user_profile/tests/test_censo_sync.py`.

## Description

- Moved censo refresh/apply bucket-event emission out of the config CLI transport and into `CensoSyncService`.
- Added `build_censo_sync_service` as the production application-service builder that wires bucket-scoped event history.
- Kept config CLI censo commands as thin transport functions that resolve profile/bucket, call the service, and emit typed output.
- Added service-level regression coverage proving production refresh enrollment writes `profile.censo.refreshed`.

## Outcome

The censo event side effect is now backend-owned and testable without duplicating bucket-event construction in the CLI layer.

## Notes

Verification passed for `src/aeat/application/user_profile/tests/test_censo_sync.py`, ruff on the touched censo service and CLI files, and locale audit.
