---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:0aa9575cc83978ca768db15c5c31f51f06247371698411b6bb7f55069584a324'
related: []
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

- the historical check passed.
- the historical check passed with 17 tests.
- the historical check passed with 1 selected runtime-migration test.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: notification locale leaves were set through
`python -m aeat.locales set`; no catalogue leaf was hand-authored.

Disposition: close `AFR-127` as `remote-mirror`.
