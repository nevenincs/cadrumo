---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ff615cd159ef54150bf62a74d69a2cd4c20d53f6c8861c19a6bbeb227a5daa47'
step_id: 'S70'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the binding gate asserting every Path-typed Settings field is either bound to a taxonomy member or declared an ExternalPathRole escape with a reason, discovered by annotation rather than name suffix so no field can hide, with a non-empty-discovery assertion so the totality check cannot pass vacuously

## Scope

- `src/cadrumo/core/tests/test_storage_binding_gate.py`
- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Add the gate asserting every `Path`-typed `Settings` field is bound to a taxonomy member or declared an `ExternalPathRole` escape with a reason, discovered by annotation rather than name suffix.
- Assert the three dispositions (member, escape, root anchor) are total, pairwise disjoint, and free of entries outliving their field.
- Add a non-empty-discovery assertion so the totality comparison cannot pass vacuously once classification derives from the taxonomy.

## Outcome

Landed in commit `3ee34dc721` (ADR R9's second supporting gate, also delivering R6's escape declarations — see S44, S47, S49).

## Notes
