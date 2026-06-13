---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S229'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s229-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S229`

Closed `AFR-127` for the live notifications snapshot service.

## Description

- Reviewed `src/aeat/application/live/_notifications.py` against the current
  secure-object live snapshot implementation.
- Corrected the affected-file row from stale `manifest-discovery` / plaintext
  metadata to `remote-mirror` with secure-object, manifest-bucket, and
  remote-provider signals.
- Verified notifications snapshots persist through the live notifications
  secure-object namespace and runtime bucket repository.
- Localized blank bucket id, blank snapshot id, not-found, and
  ambiguous-prefix refusal paths.
- Verified real-runtime tests cover secure-object persistence, legacy JSONL
  absence, SQLite ciphertext absence, bucket isolation, bounded error context,
  and read-only verb shape.
- Closed `S229` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-127` is closed as `remote-mirror`. Notifications durable state remains an
encrypted bucket-local mirror of the authenticated AEAT read surface, and the
reviewed error boundaries now follow the locale-backed and no-leak convention.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/live/_notifications.py src/aeat/application/live/test_notifications.py`
- `uv run --no-sync pytest -q src/aeat/application/live/test_notifications.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "notifications or s85_runtime"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

Locale catalogue updates were performed through `python -m aeat.locales`
(`set` and `audit`). No naked environment access, settings bypass, silent
exception swallowing, `noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail,
or tautological test was introduced.
