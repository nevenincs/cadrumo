---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:b5ffcd593bfb721df8a019b950e610cbc204d8859e246a3672bcb82e12775a12'
step_id: 'S01'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare StorageNodeKind, StorageScope, StorageLifecycle, FingerprintParticipation, and StorageOverridePolicy as StrEnums in core, gated by a test asserting each member set is closed and an unknown value is rejected at model validation

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare `StorageNodeKind`, `StorageScope`, `StorageLifecycle`, `FingerprintParticipation`, and `StorageOverridePolicy` as StrEnums in `core/_storage_taxonomy.py`.

## Outcome

Landed in commit `08c61859c0` ("declare the typed storage taxonomy as one core authority"), a single ~1179-line commit that landed the whole `_storage_taxonomy.py` module at once — S01 through S09 and S18 all trace to this one commit, not a step-by-step build-out as the plan's row-by-row framing implies. Gated by `test_each_axis_is_a_closed_set` and `test_an_undeclared_axis_value_is_rejected_at_model_validation` in `test_storage_taxonomy.py`.

## Notes
