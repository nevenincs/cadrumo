---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S210'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s210-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S210`

Closed `AFR-108` for the filing application runtime repository helper.

## Description

- Reviewed `src/aeat/application/filing/_runtime_repository.py` against the
  `runtime-default` classification for secure-object, active-profile, and
  manifest-bucket signals.
- Centralized the no-active-profile locale key used by filing application
  repository resolution.
- Added structured refusal context that distinguishes a blank explicit bucket
  from a missing active profile bucket.
- Extended `src/aeat/application/filing/test_runtime_repository.py` to pin both
  context values while preserving real runtime refusal coverage.
- Closed the plan step through the vaultspec CLI and aligned the AFR register
  entry with the recorded closure.

## Outcome

`AFR-108` is closed as `runtime-default`. The helper still defers the concrete
secure-object adapter import until runtime and routes bucket storage through
`secure_object_repository_for_bucket()`. Refusal paths now carry typed
`ModeloApplicationError` metadata with a centralized translated-message key and
specific context for operators and diagnostics.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/application/filing/test_runtime_repository.py`
- `uv run --no-sync pytest -q src/aeat/application/filing/test_runtime_repository.py src/aeat/application/filing/test_review_runtime_storage.py`
- `uv run --no-sync ruff check src/aeat/application/filing/_runtime_repository.py src/aeat/application/filing/test_runtime_repository.py`
- `uv run --no-sync ruff check src/aeat/application/filing/_runtime_repository.py src/aeat/application/filing/_history_repository.py src/aeat/application/filing/_review.py src/aeat/application/filing/test_runtime_repository.py src/aeat/application/filing/test_review_runtime_storage.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No direct production `SecureObjectRepository` construction, naked environment
access, settings bypass, silent exception swallowing, raw user-facing string,
`noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail, or tautological test was
introduced.

Observed follow-up: the domain filing runtime helper has a parallel bucket
resolution shape and remains tracked under its own `AFR-238` row. This S210
slice did not merge that helper because the current owner row is limited to the
application filing runtime boundary.
