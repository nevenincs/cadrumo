---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S150'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S150 Censo Event Enrollment Boundary

## Scope

Move profile censo bucket-event emission out of the config CLI and into the user-profile application service boundary.

## Description

- Moved CENSO_REFRESHED and CENSO_APPLIED bucket-event emission into `CensoSyncService`.
- Kept concrete bucket-event repository wiring in `_profile_censo.py` so application code does not import persistence adapters.
- Avoided adding a new public user-profile compatibility factory or facade export.
- Updated the censo apply docstring to state that the application service emits `CENSO_APPLIED`.

## Outcome

The CLI censo module no longer authors bucket-event payloads. Refresh and apply event emission is application-owned by `CensoSyncService`, while the CLI remains the concrete composition point for bucket-scoped storage wiring.

## Notes

Verification covered the application censo service tests, marker-enabled CLI censo tests, ruff, compileall, architecture-boundary tests, and the hard size-budget guard.
