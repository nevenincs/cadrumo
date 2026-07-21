---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S219'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-002 localise 'No pending filing obligation for this profile' refusal on aeat app modelo work file to es ca hu per profile output_language

## Scope

- `currently English only`
- `src/aeat/entrypoints/cli/_modelo.py`

## Description

- Ground the refusal path with `vaultspec-rag` and confirm the abort summary sources in `src/aeat/application/workflow/_deadline_stage.py`, `src/aeat/application/workflow/_engine.py`, and the modelo error boundary.
- Route `ModeloWorkflowGateError` for `NO_PENDING_OBLIGATION` through the registered locale message instead of exposing the raw workflow summary as the public exception message.
- Move the registered workflow-gate message key to `application.modelo.errors.workflow_gate_no_pending_obligation` and update `en`, `es`, `ca`, and `hu` catalogues through `aeat.locales`.
- Add renderer-level coverage for Spanish, Catalan, and Hungarian output languages while preserving `NO_PENDING_OBLIGATION` and `ABORTED` machine context.
- Add regression coverage proving other workflow abort reasons still render their workflow summary rather than the no-pending-obligation locale key.
- Tighten the existing `work file` CLI UX regression to request Catalan output and assert the raw English refusal does not surface.

## Outcome

- Operator-facing `aeat app modelo work file` no-pending filing-obligation refusals now render the human message through the active output language.
- The live workflow result, abort reason, stage, and suggestion contract remain stable; `error.result.summary` still carries the original workflow summary for internal telemetry.
- Locale scaffold and audit gates pass after retiring the old generic workflow-gate locale key.

## Notes

- Validation passed: `uv run --no-sync ruff check src/aeat/application/modelo/_action_errors.py src/aeat/core/errors/registry/_domain_part2.py src/aeat/application/modelo/tests/test_workflow_gate_error_boundary.py src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py`.
- Validation passed: `uv run --no-sync pytest src/aeat/core/errors/tests/test_registry.py src/aeat/application/modelo/tests/test_workflow_gate_error_boundary.py -q`.
- Validation passed: `uv run --no-sync python -m aeat.locales scaffold --check`.
- Validation passed: `uv run --no-sync python -m aeat.locales audit`.
- Integration check attempted: `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_file_defaults_to_current_verified_for_visible_target -m integration`; it failed before the exercised refusal because current registry validation rejects singleton `irpf_pf_modulos_*_unidades` semantic roles while creating the prerequisite work unit.
