---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S229]]'
---

# `secure-storage-production-hardening` `W12.P26.S229` Review

## S229-001 | PASS | Notifications snapshots are encrypted remote mirrors

`NotificationsService` persists authenticated AEAT notification snapshots
through `SecureSnapshotRepository`, `LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE`,
and `secure_object_repository_for_bucket()`. The reviewed module no longer owns
a plaintext JSONL side store and does not construct SQL routes, read naked
environment variables, or expose an AEAT-side mutation verb.

## S229-002 | PASS | Affected-file metadata is corrected

The affected-file register had stale `manifest-bucket, plain-file` signals and
a `manifest-discovery` target. Source review confirms the current surface is a
secure-object remote mirror, matching the live snapshot migration and namespace
registry policy. The plan row is corrected to `secure-object, manifest-bucket,
remote-provider`, target `remote-mirror`, owner `W12.P24.S98`.

## S229-003 | PASS | Refusals are localized and bounded

Blank bucket id, blank snapshot id, not-found, and ambiguous-prefix paths carry
application-live notification locale keys. Lookup refusals avoid leaking bucket
ids or matched full snapshot ids; tests assert the bounded context directly.

## S229-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/live/_notifications.py src/aeat/application/live/test_notifications.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/live/test_notifications.py` passed with 17 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "notifications or s85_runtime"` passed with 1 selected runtime-migration test.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: notification locale leaves were set through
`python -m aeat.locales set`; no catalogue leaf was hand-authored.

Disposition: close `AFR-127` as `remote-mirror`.
