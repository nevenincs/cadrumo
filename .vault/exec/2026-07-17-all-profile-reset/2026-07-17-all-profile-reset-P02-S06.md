---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Define durable non-secret reset operation, target phase, pointer snapshot, retention, marker, and summary models

## Scope

- `src/cadrumo/application/_config_reset_models.py`

## Description

- Define the durable, credential-free reset-journal record shapes: `ConfigResetOperation` (schema-versioned, sorted-unique targets, pointer snapshot, optional pause reason / summary), `ConfigResetTarget`, `ConfigResetPointerSnapshot`, `ConfigResetRetentionDecision`, `ConfigResetDeletionMarker`, and `ConfigResetSummary`.
- Type every closed axis as a core-style StrEnum: `ConfigResetOperationStatus` (incomplete/paused/complete), `ConfigResetTargetPhase` (snapshotted → retention_approved → auth_clearing/cleared → pointer_reconciling/reconciled → deleting → deleted), and `ConfigResetPauseReason`.
- Enforce record invariants in model validators without asserting state-transition rules: pointer presence must match bucket id + content digest; retention blocking flag must match retained count and override approval must carry exactly one reason and only when a record blocks erase; a deleting target requires exactly one marker whose bucket id matches; a complete operation requires every target deleted with reconciling summary counts and a completion timestamp matching the operation update; a paused operation requires exactly one pause reason and one or more sorted-unique paused target ids drawn from the target set.
- Add `new_config_reset_operation_id` generating a 256-bit lowercase-hex identifier via `secrets.token_hex`.

## Outcome

The models are the durable non-secret state P02.S07 persists and P03 orchestrates: they carry no credentials, snapshot the deletion fingerprint (`BucketDeletionFingerprint`) and approved retention decision per target, and pin the schema version to a `Literal[1]` so a future shape is refused rather than silently read (forward-only, no legacy tolerance). Exercised end to end by the P02.S08 real-filesystem suite and the P01.S05 journal-ownership tests (86 tests green across bucket_maintenance + config_reset); ruff clean.

## Notes

Landed in commit `11356b4792`; this record grounds it and re-verifies at HEAD. The module docstring is explicit that these are record contracts with local invariants only — no orchestration, discovery, transition enforcement, resume, or completion semantics live here; those are P03's `config_reset.py`.
