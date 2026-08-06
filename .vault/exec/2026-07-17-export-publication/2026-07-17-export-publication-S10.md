---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:b8783a01480035af746b13b55ec4076e9c291fb7351839b1ab61ec74517c565c'
step_id: 'S10'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

# Gated requirement surfaced by the export durable-layer review, latent until S07 wires both export doors through the shared service: make reconcile_prepared_exports hold the per-destination lock (or a repository lock spanning staged-temp removal and journal delete) per operation, or guarantee the S07 call site runs reconcile only at exclusive startup, so a reconcile concurrent with a live same-target export cannot unlink the live staged temp and spuriously fail os.replace with a ProfileExportError

## Scope

- `the gate is a test that holds the destination lock and proves reconcile does not remove the live staged temp or raise a spurious ProfileExportError`
- `src/cadrumo/application/user_profile/_bundle_export.py`
- `src/cadrumo/application/user_profile/tests/test_bundle_export_recovery.py`

## Description

- Make `reconcile_prepared_exports` acquire the same per-destination lock a live `export_profile_bundle` holds across its whole publication, non-blocking (`timeout=0`).
- Skip any operation whose target lock is held: it is an in-flight export, not a crash orphan, so reconcile must not touch its staged temp or journal.
- Re-read the operation under the lock via `_reload_prepared_operation`; clear it only while still prepared, and clear a bare orphan whose parent directory is gone without a lock.
- Add a real-behavior proof: a reconcile run while the destination lock is held leaves the live staged temp and journal untouched and returns nothing, then clears the operation once the lock is released.

## Outcome

Closes the LOW-1 race from the durable-layer review: a reconcile concurrent with a live same-target export can no longer unlink the live staged temp or delete its journal and so can no longer fail the live `os.replace` with a spurious `ProfileExportError`. The recovery suite (seven cases including the new held-lock proof) passes. Committed in `5aac909a78`.

## Notes

The lock is the same destination sidecar the live publication holds, so the two are genuinely mutually exclusive; a per-operation-id lock would not be. No production caller wires reconcile yet, so the race was latent; the lock makes reconcile safe to call at any time. The three-phase COMPLETED-journal wire and the un-audited-egress observation are tracked separately as plan step S11.
