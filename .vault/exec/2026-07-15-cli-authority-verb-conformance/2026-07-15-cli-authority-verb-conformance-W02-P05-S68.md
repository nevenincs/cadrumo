---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S68'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---
# Prove target discovery includes live, tombstoned, and dangling-pointer buckets but excludes cold defaults

## Scope

- `src/cadrumo/application/tests/test_config_reset.py`

## Description

- Create two real profile buckets, tombstone one through the profile lifecycle authority, and point the active-profile record at a third UUID whose bucket is absent.
- Place a cold default `cadrumo.db` sentinel with known bytes at the local-storage root before starting reset.
- Run the real confirmed all-profile reset and inspect its durable journal, target phases, deletion markers, pointer outcome, secure-storage cleanup, and bucket directories.
- Assert discovery returns the sorted live, tombstoned, and dangling-pointer UUID targets while never treating the cold default database as a bucket.
- Assert reset leaves the cold default file and its exact bytes unchanged.

## Outcome

- The focused discovery proof passed with one live bucket, one tombstoned bucket, and one dangling-pointer UUID represented in the durable reset operation.
- The operation completed with three targets, two physical deletions, one already-absent target, and every target persisted at the `deleted` phase.
- The active pointer, existing target directories, acquisition lock, and selected-profile certificate-secret blobs were removed through their real authorities.
- The root-level `cadrumo.db` sentinel was excluded from target discovery and retained byte-for-byte.
- The focused reset command completed as part of a 14-test run covering S68-S70: 14 passed in 100.87 seconds.

## Notes

- The proof uses real profile lifecycle, pointer, auth-lock, encrypted secret-storage, bucket-maintenance, and reset-journal behavior; it introduces no fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored reset logic.
- No source, plan, user documentation, or generated documentation path was changed while curating this record.
