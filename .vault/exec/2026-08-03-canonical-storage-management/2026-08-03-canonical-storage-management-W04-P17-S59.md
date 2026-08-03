---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:08f926ef77cf7c7101e6d05f35d251ef021bbeb7db480af43df6b6a6e4e07c40'
step_id: 'S59'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the containment proof that with no active profile no category reclaim accepts resolves inside a bucket, keystore, or financial-sensitivity location, derived from the declared axes rather than listing today's members so a future prunable bucket-scoped member cannot silently join the accepted set

## Scope

- `src/cadrumo/application/storage_management/tests/`

## Description

- Retire the two `skipif` platform markers (violating the no-skip gate) into the guarded-inline shape the materialiser mode-bit test already used.
- Add the containment proof: derive the accepted-reclaim set by invoking the real verb over every declared taxonomy member, asserting over axes (not bucket- or keystore-scoped, resolves inside the bucket container, not state-grouped, not unbounded-lifecycle) rather than a listed set, plus a no-accepted-path-contains-a-refused-path check.

## Outcome

Landed in commit `9c7db494bb`.

## Notes
