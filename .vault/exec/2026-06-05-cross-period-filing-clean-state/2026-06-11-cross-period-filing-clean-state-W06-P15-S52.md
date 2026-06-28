---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S52'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W06.P15.S52` exec - workflow evidence grounding

## Description

Cover import-flow refusal when justificante-backed evidence has no persisted artifact.
Cover import-flow refusal when the persisted justificante belongs to a different filing period.
Cover Modelo 390 export reaching ordinary draft validation after every upstream Modelo 303 filing is imported with bound justificante evidence and matching filed observations.
Preserve legacy/drifted clean-state tests by seeding dangling filing records directly instead of using the stricter production import path.

## Outcome

Workflow coverage now proves the import-to-filing path and the clean-state gate agree on evidence grounding. Properly imported upstream justificante-backed filings clear the cross-period evidence gate; missing or mismatched artifacts fail before a new filing record is stamped.

## Verification

Command passed: `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py -q` with 88 tests passing.

Command passed: `uv run ruff check` on the touched calculation, Modelo action, CLI, deadline, workflow-gate, and focused test surfaces.

Command passed: YAML parse check for `src/aeat/locales/en.yml` and `src/aeat/locales/es.yml`.

## Notes

The synthetic Modelo 390 export test intentionally stops at ordinary draft validation after clean-state passes, because the test revision does not populate a complete official export payload. The final gate also includes wrong-taxpayer import and clean-state regressions so non-member justificante evidence cannot be substituted across taxpayer buckets.
