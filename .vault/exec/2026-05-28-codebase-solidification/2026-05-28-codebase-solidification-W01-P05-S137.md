---
step_id: S137
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
---

# codebase-solidification W01.P05.S137 step record

## Step

Split `_ensure_utc` into `_coerce_utc_aware` and `_validate_utc_aware`; move both to a canonical module under `aeat.core.time`; `src/aeat/core/time/_utc.py`.

## Outcome

Created `src/aeat/core/time/__init__.py` and `src/aeat/core/time/_utc.py` with:

- `_coerce_utc_aware(value: datetime) -> datetime` — coerces naive datetimes to UTC-aware by attaching `datetime.UTC`; converts offset-aware datetimes via `astimezone(UTC)`. Maps to the certificate.py semantic.
- `_validate_utc_aware(value: datetime) -> datetime` — raises `CoreValidationError` on naive datetimes or datetimes whose UTC offset is non-zero. Maps to the persistence boundary semantic found in `_manifest.py`, `_recovery_record.py`, and `_aggregate.py`.

Call-site migration is deferred to S139 per plan scope.

## Verification

- Collision check: no peer WIP found on `src/aeat/core/time/` at dispatch time.
- Pytest: 10 tests passed (`src/aeat/core/time/test_utc.py`).
- Commit: `2e0d737a2`
