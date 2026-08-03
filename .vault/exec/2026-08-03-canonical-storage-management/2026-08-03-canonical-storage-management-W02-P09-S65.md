---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:3991cf3418a6c5fb2f77fec3206a89060779168f2d13e00c0031abfc416d71f6'
step_id: 'S65'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare fingerprint_participation as its own StorageLocation field, orthogonal to lifecycle and grouping, and derive the drift-fingerprint exclusion set from it instead of eight hardcoded settings reads, deliberately including the compiled registry pickle so a recompile no longer churns the digest, gated by both behavioural halves: a write beneath an excluded category leaves the digest unchanged and a write beneath a participating one moves it

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`
- `src/cadrumo/core/observability/_fingerprint.py`

## Description

- Add `fingerprint_participation` as an independent `StorageLocation` field.
- Derive the drift-fingerprint exclusion set from it instead of eight hardcoded settings reads, deliberately including `cache/registry` (the compiled registry pickle) in the participating set.
- Gate with both behavioural halves: exclude leaves the digest unchanged, participate moves it.

## Outcome

Landed in commit `f7493b4431`. One visible consequence per ADR R16: `db_sha256` differs from its pre-campaign value on any machine holding a compiled registry cache, and stamped run traces refuse replay once — the drift-refusal mechanism working as designed, not a regression.

## Notes
