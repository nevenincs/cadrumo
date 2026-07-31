---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:768c18489908f22f5b0010cfc01130bfdd1e1bee40b0827fc9ed1a75b43fb6d3'
step_id: 'S70'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---
# Prove sorted locking, writer pauses, reset exclusion, retention recheck, and renewed confirmation with real processes

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_lockfile.py`
- `src/cadrumo/adapters/persistence/storage/bucket/tests/test_lockfile.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_ephemeral.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_provider_session.py`
- `src/cadrumo/application/bucket_maintenance/_service.py`
- `src/cadrumo/application/tests/test_config_reset_concurrency.py`

## Description

- Hold the lexically later profile B bucket lock in a real child process, then start reset in another child and observe that reset has acquired profile A's canonical lock while it waits for B.
- Invoke the real `BucketMaintenanceService.rename` writer in a third child against profile A and prove its production `profile_storage_session` provider path is refused by the same canonical bucket lock within the shorter writer timeout.
- Assert the blocked reset times out on profile B, releases profile A, creates no journal, and leaves exact pointer bytes, fingerprints, and profile label unchanged.
- Exercise the canonical lock substrate's same-thread reentrant depth and final-release behavior so nested application writers compose one lock authority while a different thread remains excluded.
- Start a retention-blocked reset in a fresh process and prove a second fresh reset start is excluded without changing the existing journal.
- Mutate the real filed-record catalogue between start and resume, refuse an unconfirmed fresh-process resume without journal mutation, then recheck fingerprint and retention under renewed confirmation.
- Require confirmation again after the changed-state pause, require a new retention override for the updated retained-record count, and complete the same operation only after both approvals are supplied.

## Outcome

- The sorted-lock proof observed profile A locked while reset waited on the pre-held profile B lock, demonstrating acquisition order across the two UUID targets.
- The real rename writer was refused on profile A after its one-second timeout while reset remained active, proving provider-session writers and reset share the canonical bucket lock.
- Reset then refused on profile B after its configured fifteen-second timeout and unwound without a journal or mutation to either target, the active pointer, or the profile label.
- The fresh-process lifecycle proof refused an overlapping start, detected a newly filed record through a changed fingerprint and increased retention count, required renewed confirmation, paused again without a renewed retention override, and completed only after the override was explicitly resupplied.
- Both concurrency tests passed as part of the 14-test S68-S70 run: 14 passed in 100.87 seconds.
- The focused canonical lock and bucket-session support suite also passed: 25 passed in 9.36 seconds.

## Notes

- `BucketMaintenanceService.rename` is the production application writer under test; the proof does not substitute a synthetic write loop or directly duplicate rename business logic.
- The same-thread reentrant lock preserves one physical lockfile until final depth, while same-process different-thread and cross-process contenders remain excluded.
- All process synchronization uses real lock acquisition, bounded polling, process pipes, and production timeouts; no fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored business logic was introduced.
- No source, plan, user documentation, or generated documentation path was changed while curating this record.
