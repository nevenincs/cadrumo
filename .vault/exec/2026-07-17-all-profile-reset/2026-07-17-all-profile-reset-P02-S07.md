---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:b6965780a2cf6e9356a491eee4c00eba743ab3b6af35efa5a288aa901d7374a0'
step_id: 'S07'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Persist reset journals atomically outside target directories with restrictive permissions and corruption refusal

## Scope

- `src/cadrumo/application/_config_reset_repository.py`

## Description

- Persist each journal as an individual file under `<storage-root>/reset-operations/`, outside every bucket directory, one operation per `<operation_id>.json`.
- Write atomically through `atomic_write_hardened_text` (staged temp + replace) with restrictive modes: `0700` on the journal directory, `0600` on each file, with the POSIX-only nature of the chmod documented and no `.tmp` residue left behind.
- Refuse corruption at load: missing/unreadable files, malformed JSON, schema-invalid payloads, a future `schema_version`, and a filename-vs-payload operation-id mismatch all raise `ConfigResetJournalCorruptError`.
- Guard the location: refuse a symlinked/junctioned journal root or file, refuse a root that resolves outside the storage root or into the buckets tree, so a link cannot redirect journal bytes into a deletion target.
- Provide the orchestration-facing surface under an exclusive repository lock: `create` / `create_exclusive` / `refuse_if_incomplete` (overlap refusal), `save`, `load`, `list` (started_at-ordered), `incomplete`, `latest`, per-operation `operation_lock`, and `verify_deletion_ownership` (target existed with the expected fingerprint, carries an approved retention decision, and holds a matching deleting/deleted marker).

## Outcome

The repository is the single durable-state writer P03 composes: it never stores credentials, keeps atomicity scoped honestly to the individual journal-file write (not the whole multi-bucket operation, which the docstring states plainly), and exposes the ownership check P01's `_delete_locked` already delegates to. Typed errors are registered core `CadrumoError` subclasses. Proven by the P02.S08 real-filesystem + real-subprocess suite (11 tests); full bucket_maintenance + config_reset suites green (86 tests); ruff clean; collection clean.

## Notes

Landed in commit `11356b4792` with the error codes registered in `b7b27b1f91` (fix(errors): register ConfigResetJournal* error codes). This record grounds the landed work and re-verifies at HEAD. `_validate_existing_root` is documented as a location check, not protection against malicious concurrent path replacement — an honest boundary statement, not a gap.
