---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr]]"
---

# W80 file workflow gate execution

## Scope

Implemented and adjudicated W80 as WorkflowEngine-only preflight routing for modelo verify/file. `file_modelo_revision` now runs the real workflow engine gate before creating internal filing state. `verify_modelo_revision` runs the same gate after local completeness grants and before verification report/state persistence. The gate validates a revision-backed filing draft from the immutable calculation revision output, approves a `READY_TO_SUBMIT` draft using the existing filing review service, runs `WorkflowEngine.run_for_period`, persists the resulting workflow run, and raises a typed `ModeloWorkflowGateError` without writing downstream lifecycle state when the workflow aborts.

The adjudicated implementation path is WorkflowEngine-only preflight behind `verify_modelo_revision` and `file_modelo_revision`; no standalone preflight command, direct modelo `SubmissionEngine.preflight` action, `aeat workflow` root, or `aeat run` root was added.

## Baseline

Read the apex CLI ADR §4.3 and §8, the workflow-engine-harvest ADR, and the workflow-resumption-semantics ADR. Baseline verification found:

- `file_modelo_revision` previously transitioned verified revisions directly to filing records.
- `verify_modelo_revision` and `file_modelo_revision` had no workflow/preflight invocation.
- workflow-level resume contracts from W59 existed, but no modelo-level resume action or CLI verb existed.
- root `aeat workflow`, root `aeat run`, and `app modelo preflight` were absent.

## Implementation

- Added the modelo workflow gate in `src/aeat/application/modelo/_actions.py`.
- Added `ModeloWorkflowGateError` and exported it from `src/aeat/application/modelo`.
- Built the workflow gate from real services: `DeadlineEngine`, registry runtime schema provider, `FilingValidator`, filing `approve_draft`, selected auth provider, `SubmissionEngine`, and `WorkflowEngine`.
- Persisted every workflow result through `save_run`.
- Routed `verify_modelo_revision` through the same workflow gate after local completeness grants and before verification report/state persistence.
- Switched the gate's draft builder to validate immutable `CalculationRevision` output so relation-fed annual summaries such as Modelo 180 are not recomputed from incomplete raw inputs.
- Added Modelo 180 deadline schedule/window support needed by the real workflow deadline gate.
- Added real-behavior tests proving:
  - workflow auth/preflight abort happens before filing state writes;
  - workflow auth/preflight abort happens before verify report/state writes;
  - Q4 filing windows crossing into January use the work unit filing year while still evaluating against the actual filing date;
  - existing file, amend, import, and history flows continue to pass through encrypted repositories.

## Review remediation

Code review found that the first implementation resolved the workflow schedule from the actual filing date year, which broke year-crossing windows such as Modelo 130 2026 4T filed in January 2027. The fix introduced a modelo-owned deadline adapter that delegates to `DeadlineEngine.compute` with the work unit `filing_year`, while preflight deadline checks continue evaluating the actual `today` date.

The reviewer also noted unrelated dirty changes in the shared workspace. They were not part of this W80 slice and were not reverted.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py src/aeat/application/modelo/test_history.py`
- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/__init__.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_amend_flow.py src/aeat/application/modelo/test_import_flow.py`

## Rows Closed

- `W80.P385.S2204`
- `W80.P385.S2205`
- `W80.P385.S2206`
- `W80.P385.S2207`
- `W80.P386.S2209`
- `W80.P388.S2219`
- `W80.P388.S2220`
- `W80.P389.S2227`
- `W80.P389.S2228`

## Still Open

No W80 R14/R15/R16 adjudication rows remain open for verify/file preflight routing.
