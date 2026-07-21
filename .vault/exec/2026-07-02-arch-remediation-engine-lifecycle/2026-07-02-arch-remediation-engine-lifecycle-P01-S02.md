---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Dispose the bucket engine on session close and on profile switch through the same path that invalidates session state, so the two lifecycles cannot diverge

## Scope

- `src/aeat/adapters/persistence/storage/runtime.py`

## Description

- Dispose the registered engine handle and sweep the bucket's cached engines in `BucketSession.close`
  via `dispose_engine_handle` / `dispose_engines_for_bucket`.
- Bind disposal to the same close path that seals the session, so close and profile switch dispose the engine identically.

## Outcome

Engine disposal is bound to the session close/switch boundary; the two lifecycles cannot diverge.

Landed in commit `38e62c216`.

## Notes

Replaced the old `_evict_engine` settings-derivation path (and its `_evict_all_engines` fallback) with bucket-identity disposal.
