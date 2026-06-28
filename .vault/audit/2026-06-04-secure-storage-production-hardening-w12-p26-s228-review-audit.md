---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S228]]'
---

# `secure-storage-production-hardening` `W12.P26.S228` Review

## S228-001 | PASS | Expedientes snapshots are encrypted remote mirrors

`ExpedientesService` persists AEAT-origin declaration-register captures through
`SecureSnapshotRepository` and `secure_object_repository_for_bucket()`, under
the `LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE` namespace. The reviewed service does
not write plaintext JSONL files, construct SQL routes directly, read naked
environment variables, or expose an AEAT-side mutation verb.

## S228-002 | PASS | Lookup refusals no longer leak bucket or full snapshot ids

Expedientes lookup misses and ambiguous-prefix refusals now carry locale-backed
`translated_message` metadata and bounded context. The not-found path records
only the requested snapshot id, and the ambiguous-prefix path records the
requested prefix plus match count rather than the matched full ids.

## S228-003 | PASS | Object-key validation is locale-backed

Blank bucket and snapshot id guards on `expedientes_snapshot_object_key()` now
raise `LiveApplicationInputError` with application-live expedientes locale keys.
The locale leaves were scaffolded and set with `python -m aeat.locales`.

## S228-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/live/_expedientes.py src/aeat/application/live/test_expedientes.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/live/test_expedientes.py` passed with 14 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "expedientes or s85_runtime"` passed with 1 selected runtime-migration test.
- `uv run --no-sync python -m aeat.locales audit` passed.

Reviewer note: locale catalogue updates were performed through
`python -m aeat.locales set`; no catalogue leaf was hand-authored.

Disposition: close `AFR-126` as `remote-mirror`.
