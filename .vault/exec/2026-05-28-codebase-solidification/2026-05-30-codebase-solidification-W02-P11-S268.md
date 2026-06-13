---
step_id: S268
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W02.P11.S268 — RepairIntegrityError and RepairDecisionNotFoundError

## Scope

Introduce `RepairIntegrityError(CoreError)` and
`RepairDecisionNotFoundError(RepairIntegrityError)` in
`src/aeat/application/repair_integrity.py` (inline, since the module is a
flat `.py` file rather than a package). Replace four `ValueError` raises
at lines 230, 392, 415, 441 with the appropriate typed errors.

## Outcome

### New error classes

Both classes defined at module top-level in `repair_integrity.py`:
- `RepairIntegrityError(CoreError)` — integrity invariant violations
- `RepairDecisionNotFoundError(RepairIntegrityError)` — lookup miss

### Registry entries

`src/aeat/core/errors/registry/_application.py`:
- `aeat.application.repair_integrity.RepairIntegrityError` →
  code `INTEGRITY_REPAIR_INTEGRITY`, category `INTEGRITY`
- `aeat.application.repair_integrity.RepairDecisionNotFoundError` →
  code `FAIL_REPAIR_DECISION_NOT_FOUND`, category `FAIL`

### Raise sites updated

Four `ValueError` raises replaced:
- `build_repair_list_report`: flag-combination guard → `RepairIntegrityError`
- `save_decision`: content-hash mismatch on save → `RepairIntegrityError`
- `load_decision`: record not found → `RepairDecisionNotFoundError`
- `load_decision`: content-hash mismatch on load → `RepairIntegrityError`
- `list_decisions`: content-hash mismatch per-row → `RepairIntegrityError`

### Tests updated

`src/aeat/application/test_repair_integrity.py` updated to import
`RepairIntegrityError` and assert on it instead of `ValueError`.

## Locale keys

`errors.integrity.integrity_repair_integrity` and
`errors.fail.fail_repair_decision_not_found` added to all locale files.

## Files touched

- `src/aeat/application/repair_integrity.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/application/test_repair_integrity.py`
- `src/aeat/locales/*.yml`

## Collision signal

`git diff -- <target files>` before edits: no output (clean).
