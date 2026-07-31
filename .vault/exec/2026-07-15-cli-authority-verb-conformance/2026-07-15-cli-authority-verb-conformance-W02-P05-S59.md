---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:8e2421250eb73572e6b26df1a8fcfed17442da8347a17cb31c3f853673711163'
step_id: 'S59'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Define durable non-secret reset operation, target phase, pointer snapshot, retention, marker, and summary models

## Scope

- `src/cadrumo/application/_config_reset_models.py`

## Description

- Declare `ConfigResetOperationStatus`, `ConfigResetPauseReason`, and `ConfigResetTargetPhase` as closed `StrEnum` vocabularies covering incomplete, paused, and complete statuses, the three pause reasons, and the eight ordered target phases from snapshotted through deleted.
- Declare `ConfigResetPointerSnapshot` correlating pointer presence against bucket identity and content digest so a present snapshot cannot omit either field.
- Declare `ConfigResetRetentionDecision` binding the blocking flag to the retained-record count, requiring exactly one non-empty reason for an approved override, and refusing an override approved when nothing blocks erase.
- Declare `ConfigResetDeletionMarker` as the ownership witness carrying operation id, bucket id, fingerprint, and a UTC-aware mark timestamp.
- Declare `ConfigResetTarget` correlating snapshot existence against fingerprint, label, and lifecycle status, restricting a marker to the deleting and deleted phases, requiring a marker for a deleting target, and requiring exactly one completion timestamp for a deleted target.
- Declare `ConfigResetSummary` reconciling deleted and already-absent counts against the target count and bounding the override count.
- Declare `ConfigResetOperation` pinning `schema_version` to a `Literal[1]`, requiring unique sorted targets, requiring every marker's operation id to match its journal, requiring a summary exactly when complete with every target deleted and reconciled counts, and requiring a paused operation to carry exactly one reason with unique sorted paused target ids drawn from the target set.
- Add `new_config_reset_operation_id` minting a cryptographically random 256-bit hex identifier.
- Apply `STRICT_FROZEN_CONFIG` to every model and validate UTC awareness on every timestamp.

## Outcome

- The journal document is now a strict, frozen, credential-free pydantic surface: no field carries a passphrase, mnemonic, key, or decrypted payload, satisfying the non-secret design constraint.
- Structural invariants are enforced at the model boundary rather than by orchestration convention, so a journal that survives a crash cannot be reloaded in a self-inconsistent state.
- Pinning `schema_version` to `Literal[1]` makes a future or unknown version a validation refusal rather than a silently tolerated read.
- The identifier is clock-free and randomly minted, so operation identity does not depend on wall-clock time.
- Landed in commit `11356b4792`, with the pause and summary correlations extended in `60135859e2` and the validators decomposed into named helpers in `9851e08ae8`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- The models deliberately define record shape and local invariants only; phase-transition enforcement, discovery, and resume semantics belong to the orchestration step and are documented there.
