---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:70c106035e9a176a16020381c64e2e6787f857e4fb8436544947188a0124b4ce'
step_id: 'S07'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# Emit explicit applicability variants, exact occurrence entries, and tombstones that preserve prior fallback behavior

## Scope

- `dev/registry/migration`

## Description

- Reconcile exact-occurrence, continuidad, applicability, and retirement behavior with the live identity chain.
- Verify that source values remain in the shared Spanish catalogue and are not duplicated in revision schemas.
- Preserve any future semantic retirement or continuity conflict as an explicit review boundary.

## Outcome

Resolved by `ced27b5a59` and the live resolver contract. Exact occurrence keys
fall back through grounded continuidad keys and then the mandatory Spanish
source; no temporary variant/tombstone emitter is retained.

## Notes

No post-cutover staging catalogue was emitted. The historical migration row is
closed because the production contract is already the root-only outcome; a
future ungrounded retirement remains manual review, not duplicated locale data.
