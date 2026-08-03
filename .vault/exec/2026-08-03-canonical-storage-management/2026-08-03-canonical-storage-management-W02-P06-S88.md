---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:e60d2f140e30b77137ce0ad8ca6a2e52b72b426b2ce93a533fd616fa10245cd6'
step_id: 'S88'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add a RUN_RELATIVE scope axis anchored on the runs root, precedented by R13's KEYSTORE_RELATIVE and KEYSTORE_ROOT pair, and declare the three instance-scoped file leaves trace.json, envelope.json, and events.jsonl beneath it, since the run_id segment itself is a data-derived identifier excluded from R5 by the same reasoning that excludes a bucket id or content digest, while the three filenames are application-chosen and undeclared

## Scope

- `src/cadrumo/core/observability/_store.py`
- `src/cadrumo/core/observability/_sink.py`

## Description

- Declare the observability per-run trace directory's three file leaves as a governed shape.

## Outcome

Landed in the same commit as S86/S87, `3a6ce7475d`, via the grammar mechanism rather than the new `RUN_RELATIVE` scope axis this Step's action text originally called for. `run_trace` (`grammar="<root>/runs/<run_id>/trace.json"`), `run_events` (`events.jsonl`), and `run_envelope` (`envelope.json`) declare the three application-chosen filenames with `run_id` bounded to the 16-lowercase-hex shape `core.observability._context._mint_run_id` actually mints — the grammar assertion helper encodes that as a positive constraint, not a free-form placeholder, since `run_id` is a real identifier shape, not an arbitrary string. Gated by `core/observability/tests/test_run_trace_shape_conformance.py`.

## Notes

This Step's own action text asked for a new `StorageScope.RUN_RELATIVE` member, precedented by `KEYSTORE_RELATIVE`/`KEYSTORE_ROOT`. That request is now withdrawn — the honesty reviewer's own Family 3 recommendation for a new scope axis was itself retracted on finding this grammar mechanism already covers the shape, and I verified the retraction against the landed code before recording this as done rather than trusting either the original recommendation or the retraction on report alone.
