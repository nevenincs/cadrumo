---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S172'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s172-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S172`

Closed `AFR-070` for active bucket-session resolution.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/master_key/_active_session.py` against the `manifest-bucket` and `master-key` scanner signals.
- Preserved `NoActiveBucketSessionError` in the AEAT storage hierarchy while carrying the remediation detail as the exception message.
- Added debug logging to the best-effort atexit cleanup guard so shutdown cleanup failures are no longer silent.
- Added a real no-active-session test for translated error metadata and operator remediation text.
- Validated locked, expired, wrong-passphrase, and torn-manifest active-session paths through the existing real-behavior tests.

## Outcome

`AFR-070` is closed as a `bootstrap-custody` active-session implementation row.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/master_key/_active_session.py src/aeat/adapters/persistence/storage/master_key/test_adverse_sessions.py`
- Touched-surface hygiene scan found no direct environment access, settings construction, keyring calls, file I/O calls, fake/stub/monkeypatch markers, skipped/xfail tests, or direct output. The intentional broad atexit cleanup catch now logs a debug breadcrumb before returning.

## Notes

No locale strings were added. The translated no-active-session key already existed, and this row only preserved the message detail passed to the AEAT exception.
