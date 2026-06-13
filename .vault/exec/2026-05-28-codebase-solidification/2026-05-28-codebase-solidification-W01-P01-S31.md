---
step_id: S31
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S31 — narrow broad except-Exception in ledger bucket-id helpers

## Outcome

Narrowed three broad `except Exception` clauses in
`src/aeat/entrypoints/cli/_ledger.py` to `except NoActiveProfileError`
so that unexpected exceptions (e.g. `pydantic.ValidationError` from a
corrupt pointer file, `tomllib.TOMLDecodeError`) propagate unchanged to
the top-level CLI error boundary rather than being silently reclassified
as the "no active profile" refusal.

Functions fixed:
- `_ratios_bucket_id()` (line 1844)
- `_ratios_bucket_and_profile()` (line 1856)
- `_rule_bucket_id()` (line 3194)

Each now imports `NoActiveProfileError` from
`...application.workflow._errors` at call time and uses the typed except
arm. The `except` no longer catches `pydantic.ValidationError`,
`tomllib.TOMLDecodeError`, or any other non-`AeatError` exception.

Also added `get_logger` import and `_log = get_logger(__name__)` module
logger per the logging mandate.

## Narrowed exception set

`NoActiveProfileError` (subclass of `WorkflowError` → `AeatError`).

## Files touched

- `src/aeat/entrypoints/cli/_ledger.py`

## Verification

`pytest src/aeat/entrypoints/cli/test_ledger_exception_propagation.py -x` — 2 passed.
Commit: `761bc3129`.
