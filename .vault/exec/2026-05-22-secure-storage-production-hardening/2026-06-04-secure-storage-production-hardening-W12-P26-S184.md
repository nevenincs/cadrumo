---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S184'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s184-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S184`

Closed `AFR-082` for the encrypted secret-store remote-mirror boundary.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/secret_store/_secret_store.py` against the `remote-mirror` classification.
- Replaced silent cleanup suppression with DEBUG logs for benign already-missing blob cases.
- Kept cleanup failure logs redacted to digest identifiers and narrowed the atomic index-write target log to the filename.
- Added translated message keys to `SecretRecord` validation failures.
- Verified malformed secret-store indexes fail as localized storage validation errors without echoing natural keys.
- Verified miss/collision/delete errors and cleanup logs do not expose natural keys or blob digest values.
- Repaired the sensitive production file-writer inventory for the current materialisation helper, bucket lockfile PID writer, and sealed archive writer.
- Added real-behavior tests for overwrite and delete cleanup observability.
- Closed `AFR-082` and `W12.P26.S184`.

## Outcome

`AFR-082` is closed. The secret store still persists encrypted blobs plus a digest-only plaintext index, but cleanup no longer hides missing-blob events silently, validation failures follow the storage translation convention, and tests now lock down secret-key and digest redaction for miss/collision/cleanup paths.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/secret_store/_secret_store.py src/aeat/adapters/persistence/storage/secret_store/test_secret_store.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The locale CLI required `PYTHONPATH=src` because the active no-sync uv environment no longer imports the local `aeat` package and the shared `.venv` cannot currently be synced due a locked executable.

S185 is already marked closed in the shared plan by concurrent work. This S184 step did not audit or close `AFR-083`; it only touched the sensitive writer inventory because the S184 validation gate surfaced stale writer classifications in secure-storage production files.
