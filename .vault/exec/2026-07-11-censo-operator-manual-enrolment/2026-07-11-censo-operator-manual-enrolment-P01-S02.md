---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S02'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

# Retire the config profile censo pull/compare/apply/show verb family with its payloads and tests, deregister it from the profile app, and narrow CensoSyncService to the read-only afectacion projection the ledger still consumes

## Scope

- `src/aeat/entrypoints/cli/_config/_profile_censo.py`
- `src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py`
- `src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
- `src/aeat/entrypoints/cli/_config/__init__.py`
- `src/aeat/application/user_profile/_censo_sync.py`
- `src/aeat/application/user_profile/_censo_errors.py`
- `src/aeat/application/user_profile/tests/test_censo_sync.py`

## Description

- Deleted the `config profile censo` verb module `_profile_censo.py` (pull/show/compare/apply) and its payloads `_profile_censo_payloads.py` and tests `test_profile_censo_verbs.py`; deregistered the subgroup from the profile app in the config `__init__.py`.
- Narrowed `CensoSyncService` in `_censo_sync.py` to the single surviving read the ledger consumes: `bound_raw_afectacion_ratio` over the active `CensoSnapshot`. Removed `refresh_censo`, `refresh_censo_from_sede`, `show_censo`, `compare_censo_with_profile`, `apply_censo_to_profile`, the seeding/event/dropped-field helpers, and the comparison/apply/refresh result types. Kept the `aeat_censo_read` / `aeat_censo_derived` source tags (the calendar's AEAT-verified markers).
- Reduced `_censo_errors.py` to the base `CensoSyncError`; deleted the now-unraised `CensoNotAvailableError`, `CensoFieldValidationError`, `CensoApplyConflictError` and their three error-registry REFUSED entries.
- Pruned the removed symbols from the `user_profile` package `__all__` and lazy `__getattr__`, and rewrote `test_censo_sync.py` to real-behavior coverage of `bound_raw_afectacion_ratio` against a real `CensoSnapshotService`.

## Sub-decision (compare/apply retirement)

Full family retirement, per the ADR default. The live pull was the only producer of `CensoSnapshot`; with it gone, `compare`/`apply`/`show` operate on a store nothing can fill, so they were retired rather than re-seated (one enrolment path via `config profile edit`, no parallel write route). The `CensoSnapshot` / `CensoSnapshotService` substrate and `bound_raw_afectacion_ratio` were KEPT (not over-deleted): they remain live-consumed by the ledger proportional-deduction path and enrolled in the custody-carry and storage-namespace matrices, all active peer surfaces outside the ADR's scope. The ledger's censo-input point was left reading the snapshot store unchanged to avoid touching ledger semantics.

## Outcome

The `config profile censo` subgroup no longer registers; `CensoSyncService` is a thin read-only afectación projection. Ledger ratios/preflight, which construct `CensoSyncService(...).bound_raw_afectacion_ratio(...)`, are untouched and green. `test_censo_sync.py`, the ledger home-office preflight tests, and collect-only are clean.

## Notes

Landed atomically with `P01.S01`. Residual: the `CensoSnapshot` store now has no writer in production (the two refresh producers were removed), so `bound_raw_afectacion_ratio` returns `None` until a future operator-manual censo-fact capture path is added; this is a known, disclosed follow-up, not silent. The `BucketEventType.CENSO_REFRESHED` / `CENSO_APPLIED` enum members were kept (general lifecycle constants, cited by `aeat-spanish-stem-naming`) though nothing emits them now.
