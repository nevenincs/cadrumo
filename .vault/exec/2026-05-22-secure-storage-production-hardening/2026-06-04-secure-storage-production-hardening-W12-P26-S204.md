---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S204'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s204-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S204`

Closed `AFR-102` for evidence bundle models.

## Description

- Reviewed `src/aeat/application/evidence/_models.py` against the
  `manifest-discovery` classification.
- Verified the file defines typed Pydantic models and content-addressed manifest
  ids only; it does not open files, construct storage repositories, or mutate
  profile state.
- Replaced the local `"utf-8"` literal in evidence bundle id derivation with
  the centralized `UTF_8_ENCODING` constant.

## Outcome

`AFR-102` is closed. Evidence bundle model hashing remains stable while the
encoding dependency is now centralized with the rest of the storage and
manifest codebase.

Validation passed:

- `uv run --no-sync -q ruff check src/aeat/application/evidence/_models.py src/aeat/application/evidence/test_evidence.py src/aeat/application/evidence/test_ids.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/evidence/test_evidence.py src/aeat/application/evidence/test_ids.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No storage routing behavior changed. No direct secure-object repository
construction, naked environment access, silent exception swallowing, raw
user-facing strings, `noqa`, `pragma`, monkeypatches, fakes, mocks, skips, or
xfails were introduced.
