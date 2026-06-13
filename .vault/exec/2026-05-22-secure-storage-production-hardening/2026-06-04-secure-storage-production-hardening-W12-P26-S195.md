---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S195'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s195-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S195`

Closed `AFR-093` for the auth acquisition lock.

## Description

- Reviewed `src/aeat/application/auth/_acquisition_lock.py` against the
  `manifest-discovery` manifest-bucket and plain-file classification.
- Verified the lock path is derived from `Settings` and active-bucket context
  rather than direct environment access.
- Added debug logging for recoverable unreadable lock metadata during inspection
  and release cleanup.
- Replaced raw UTF-8 literals in acquisition-lock tests with
  `UTF_8_ENCODING`.
- Re-checked acquisition-lock locale coverage with `python -m aeat.locales`.

## Outcome

`AFR-093` is closed. The acquisition lock remains a deliberate profile/provider
plain-file guard for live auth flows, with settings-owned path resolution,
localized typed errors, and debug-observable recovery paths.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/auth/_acquisition_lock.py src/aeat/application/auth/test_acquisition_lock.py`
- `uv run --no-sync pytest -q src/aeat/application/auth/test_acquisition_lock.py`
- `uv run --no-sync pytest -q src/aeat/application/auth/test_ensure_session.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No repository defaults, naked environment access, monkeypatches, fakes, mocks,
test skips, or xfails were introduced. Locale keys already existed; invoking the
locale CLI normalized their YAML scalar formatting without changing message
content.
