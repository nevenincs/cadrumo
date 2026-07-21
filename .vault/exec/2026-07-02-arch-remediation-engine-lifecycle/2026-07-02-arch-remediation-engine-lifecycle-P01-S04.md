---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Narrow dispose_engine to an internal seam invoked by the session owner and the harness teardown only

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

- Add the bucket-scoped seams `dispose_engines_for_bucket` and `dispose_engine_handle`; export both through the sql and storage facades.
- Narrow the three production `dispose_engine` callers (config reset, create rollback, bucket removal) to the bucket-scoped seam.

## Outcome

No production caller disposes engines broadly; `dispose_engine` is an internal seam for the session owner and harness teardown.

Landed in commit `38e62c216`.

## Notes
