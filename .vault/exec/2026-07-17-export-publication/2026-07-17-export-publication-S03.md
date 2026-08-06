---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:940360be5140ecb8423bd3717077586be9abf5cc9bd422436b18e7ae849c76ab'
step_id: 'S03'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Implement one locked target serialization with restrictive temporary files, file fsync, durable PREPARED state, atomic replace, parent-directory fsync, post-publish COMPLETED event, and honest PREPARED recovery

## Scope

- `src/cadrumo/application/user_profile/_bundle_export.py`

## Description

- Rewrite `_bundle_export.py` to consume the typed contracts and the operation-state journal.
- Split publication into `prepare_profile_export` (resolve profile, serialize under the profile storage session, stage a restrictive `0o600` sibling temp via an `O_EXCL` staging helper, fsync it, then write the durable `PREPARED` journal) and `publish_prepared_export` (capture any prior target, atomic replace, parent-directory fsync, then the post-publish `PROFILE_EXPORTED` event, restoring the target and clearing the journal if the event fails).
- Compose both under `export_profile_bundle`, holding one exclusive lock on the resolved target across the whole publication for same-target exclusion.
- Add `reconcile_prepared_exports`, which reports every `PREPARED` operation as prepared, removes its orphan staged temp, and clears its journal, never emitting a completion event.

## Outcome

The completion event fires only after a durable atomic replace; a crash between `PREPARED` and publication recovers honestly. The pre-existing event-failure compensation semantics are preserved. Committed in `a9251f5fa2`; proven green by the S05/S06 suites.

## Notes

The staged-temp helper deliberately does not reuse the one-shot `atomic_write_hardened_*` primitive because the durable `PREPARED` journal must land between the fsynced temp and the atomic replace; the helper stages and fsyncs only, leaving the replace to publish.
