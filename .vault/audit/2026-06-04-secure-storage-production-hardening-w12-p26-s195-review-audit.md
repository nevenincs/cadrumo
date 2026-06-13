---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S195]]'
---

# `secure-storage-production-hardening` `W12.P26.S195` Review

## S195-001 | PASS | Acquisition lock stays manifest-scoped and settings-routed

`src/aeat/application/auth/_acquisition_lock.py` derives its lock path from the
caller-supplied `Settings` object plus the active bucket id. It does not read
environment variables directly and does not bypass the central settings surface.
The plain lock file remains an intentional crash-recovery guard for
cross-process live-auth acquisition, not a secure-object persistence record.

## S195-002 | PASS | Exceptions remain typed and localized

`AuthAcquisitionLockedError` derives from `AeatError`, and live operator-facing
conflicts continue to use existing `application.auth.acquisition_lock` locale
keys plus structured context. The broad write-teardown `except Exception` removes
a partially-created lock and re-raises, so it does not swallow failures.

## S195-003 | PASS | Recoverable metadata failures are observable

Unreadable/corrupt lock metadata now emits debug logs both when inspection marks
the lock recoverable and when release cleanup skips a non-owned or unreadable
lock file. This closes the silent-swallowing concern without changing lock
recovery semantics.

## S195-004 | PASS | Tests use shared constants and real behavior

The acquisition-lock tests exercise the real filesystem-backed lock path with a
validated `Settings` object and now use `UTF_8_ENCODING` instead of raw encoding
literals. No fakes, mocks, monkeypatches, skips, xfails, or tautological business
logic were added.

Validation:

- `uv run --no-sync ruff check src/aeat/application/auth/_acquisition_lock.py src/aeat/application/auth/test_acquisition_lock.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/auth/test_acquisition_lock.py` passed with 4 tests.
- `uv run --no-sync pytest -q src/aeat/application/auth/test_ensure_session.py` passed with 5 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

Reviewer note: subagent review is currently unavailable because the review agent
hit the account usage limit during the preceding S194 re-review attempt. Host
review found no remaining critical, high, medium, or low findings in the S195
slice.

Disposition: close `AFR-093`.
