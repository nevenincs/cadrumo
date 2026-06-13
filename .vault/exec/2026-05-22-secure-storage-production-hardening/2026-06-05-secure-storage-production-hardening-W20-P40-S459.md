---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S459'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P40.S459 - Implement config lock and unlock aliases

Scope: implement and localize the first-class `config lock` and
`config unlock` custody aliases through the existing profile lifecycle
session path, with real CLI coverage.

## Description

- Added explicit `config.unlock` and `config.lock` JSON payload schemas.
- Added `aeat config unlock [NAME]`, routing by profile label when supplied
  and by the active-profile pointer when omitted.
- Added `aeat config lock`, routing through the same active-profile pointer
  clear primitive used by `config profile logout`.
- Populated the new locale leaves through `python -m aeat.locales scaffold`
  and `python -m aeat.locales set`.
- Added a real subprocess CLI test covering profile create, `config lock`,
  failed default unlock with no active pointer, named unlock, and default
  unlock against the active pointer.
- Closed `W20.P40.S459` through `vaultspec-core vault plan step check`.

## Outcome

The operator-facing `aeat config unlock` and `aeat config lock` surfaces now
exist and are backed by the established profile lifecycle storage session
path. This makes existing `config unlock` guidance executable for the
lock/unlock subset.

## Notes

`W20.P40.S457` has since closed the remaining `rekey`, `recover`,
`show-recovery`, and `verify-recovery` verbs. This record remains scoped to the
lock/unlock alias slice.

Validation:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config_payloads.py src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py src/aeat/locales`
- `uv run --no-sync pytest -q -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`
- `uv run --no-sync -q python -m aeat.locales audit`
