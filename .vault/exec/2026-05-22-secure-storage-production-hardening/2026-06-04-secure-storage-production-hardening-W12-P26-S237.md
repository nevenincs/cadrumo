---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S237'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s237-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S237`

Closed `AFR-135` for the modelo work-unit history assembler.

## Description

- Reviewed `src/aeat/application/modelo/_history.py` as a read-only assembly
  surface over work-unit, calculation, filing, verification, and bucket-event
  repositories.
- Verified the module does not open files, construct direct SQL routes, read
  naked environment variables, write plaintext side stores, swallow
  exceptions, or mutate storage state.
- Kept the affected-file target as `manifest-discovery` because storage
  ownership remains in the runtime-enrolled domain repositories it reads.
- Replaced the raw missing-work-unit error string with the shared
  `application.modelo.errors.work_unit_not_found` locale metadata.
- Updated the real repository-backed history test to assert the structured
  error key and context.
- Closed `S237` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-135` is closed as `manifest-discovery`. No storage migration was required:
the history assembler has no durable state of its own and consumes the existing
runtime secure-object repositories. The one user-facing refusal path now follows
the localized error convention used by the rest of the modelo work-unit API.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_history.py src/aeat/application/modelo/test_history.py`
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_history.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No new locale key was needed; the assembler now reuses the existing modelo
work-unit-not-found key. No naked environment access, settings bypass, silent
exception swallowing, `noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail,
or tautological test was introduced.
