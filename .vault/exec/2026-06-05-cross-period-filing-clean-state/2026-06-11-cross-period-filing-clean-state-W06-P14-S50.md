---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S50'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W06.P14.S50` exec - import artifact binding

## Description

Require `aeat_justificante_pdf` and `aeat_live_capture` imports to resolve a persisted justificante artifact.
Reject missing justificante artifacts before stamping a filing record as AEAT-accepted.
Reject persisted justificante artifacts whose modelo, ejercicio, or period do not match the work unit being imported.
Leave CSV-register imports on their existing reference-only path because they are not justificante-verified evidence.
Add localizable error keys for missing and mismatched justificante artifacts.

## Outcome

The external import path now produces filing records that satisfy the same evidence-resolution contract as cross-period clean-state evaluation. Operators cannot create a new justificante/live-backed filing record from a bare reference id alone.

## Verification

Command passed: `uv run pytest src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_import_flow.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py -q` with 88 tests passing.

Command passed: `uv run ruff check` on the touched calculation, Modelo action, CLI, deadline, workflow-gate, and focused test surfaces.

Command passed: YAML parse check for `src/aeat/locales/en.yml` and `src/aeat/locales/es.yml`.

## Notes

The focused gate exposed active period-standardisation drift in deadline windows. The workflow and deadline boundaries now tolerate both typed `Period` values and transitional string window tokens while preserving typed output. A follow-up review found non-member taxpayer identity was not yet bound to justificante evidence; the final implementation now requires expected taxpayer id at the import boundary and during clean-state matching.
