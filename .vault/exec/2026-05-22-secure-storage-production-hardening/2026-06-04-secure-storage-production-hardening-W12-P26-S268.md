---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S268'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s268-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S268`

Closed `AFR-166` for profile orchestration runtime-default custody.

## Description

- Audited `src/aeat/application/user_profile/_orchestration.py` as the profile lifecycle coordinator over runtime-owned secure-object repositories, active-profile pointer custody, and bucket directory cleanup.
- Verified secure-object writes remain delegated to profile repositories and lifecycle services under profile storage sessions.
- Added debug evidence before the intentional missing-active-record degradation returns `None`.
- Replaced the rendered bare `OSError` bucket-directory cleanup refusal with an AEAT user-profile error carrying a locale key and structured context.
- Added the new translation key through `python -m aeat.locales set` for English, Spanish, Catalan, and Hungarian.
- Added a real lifecycle-storage-span test for the missing-record degradation.

## Outcome

`AFR-166` is closed as `runtime-default`. The orchestration layer continues to own the
profile lifecycle coordination boundary, while profile records and event history remain
routed through runtime-owned repositories. Remaining user-profile repository topology
work stays tracked by `W12.P26.S269` through `W12.P26.S271`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_orchestration.py src/aeat/application/user_profile/test_orchestration.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_orchestration.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_orchestration_pointer.py`
- `uv run --no-sync ruff check src/aeat/application/user_profile/test_orchestration_pointer.py`
- `PYTHONPATH=src uv run --no-sync python -m aeat.locales audit`

## Notes

No manual locale editing was used for the new key. The broader plan check still reports
only the existing `PLAN022` monotonic-order warning.
