---
step_id: S35
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S35 — wrap _record_unhandled with build_error_envelope

## Outcome

Introduced `UnhandledWorkflowError(WorkflowComponentError)` in
`src/aeat/application/workflow/_errors.py`. Registered it as
`INTERNAL_WORKFLOW_UNHANDLED` (category `INTERNAL`) in
`src/aeat/core/errors/registry/_application.py` with
`message_key="errors.internal.internal_workflow_unhandled"`. Added locale
message keys to all four locale files (en, es, ca, hu) via
`python -m aeat.locales scaffold` then `python -m aeat.locales set`.

Modified `_record_unhandled` in `src/aeat/application/workflow/_engine.py` to:
- construct a synthetic `UnhandledWorkflowError` carrying `stage`, `error_type`,
  and `error_message` in its context
- call `build_error_envelope(synthetic)` immediately, producing a structured
  `ErrorEnvelope` with `code="INTERNAL_WORKFLOW_UNHANDLED"` for telemetry
- raise `WorkflowAbortSignalError` from the synthetic error (chain: original ->
  UnhandledWorkflowError -> WorkflowAbortSignalError)

All 6 `_record_unhandled` call sites (lines 498, 708, 776, 829, 851, 1140 in
`_engine.py`) are covered by this single change to the centralised helper.

## Files touched

- `src/aeat/application/workflow/_errors.py` — `UnhandledWorkflowError` added
- `src/aeat/application/workflow/_engine.py` — `_record_unhandled` updated; import of `build_error_envelope` and `UnhandledWorkflowError` added; `WorkflowComponentError` import removed (no longer used)
- `src/aeat/core/errors/registry/_application.py` — `INTERNAL_WORKFLOW_UNHANDLED` entry added
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml` — locale key added

## Verification

`uv run --no-sync pytest src/aeat/application/workflow/test_engine.py -x`: 46 passed

## Commit

`8fd526d02`
