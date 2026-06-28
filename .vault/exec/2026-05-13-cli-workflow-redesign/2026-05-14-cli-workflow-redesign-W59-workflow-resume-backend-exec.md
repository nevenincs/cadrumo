---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S1741-S1746-S1759-S1760-S1764'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-workflow-engine-harvest-adr]]'
---

# `cli-workflow-redesign` `W59` workflow resume backend slice

Completed the backend-owned workflow-resumption foundation without adding a CLI shim or duplicating modelo lifecycle behavior.

- Modified: `src/aeat/application/workflow/_resume.py`
- Modified: `src/aeat/application/workflow/_models.py`
- Modified: `src/aeat/application/workflow/_engine.py`
- Modified: `src/aeat/application/workflow/_persistence.py`
- Modified: `src/aeat/application/workflow/__init__.py`
- Modified: `src/aeat/application/workflow/test_resume.py`
- Modified: `src/aeat/application/workflow/test_models.py`
- Modified: `src/aeat/application/workflow/test_persistence.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Baseline verification found the W59 backend resume action existed but was only a context helper. The missing backend pieces were strict command/result/log contracts, persisted resume linkage, and real secure-storage verification that did not rely on environment patching.

This slice keeps ownership in `aeat.application.workflow`:

- `WorkflowResumeCommand` accepts only workflow-engine run ids.
- `WorkflowResumeResult` returns the prior run id, modelo, period, obligation, aborted reason, context, and log fields.
- `WorkflowResumeLogFields` records stable non-secret resume metadata.
- `WorkflowResult.resumed_from` records the prior workflow run id and refuses self-references.
- `WorkflowEngine.run_for_period(..., resumed_from=...)` carries the linkage into the produced workflow result.
- `WorkflowEngine.run_for_period` validates malformed resume-link values before running workflow stages.
- Workflow-run persistence accepts an injected real `SecureObjectRepository` so tests can exercise encrypted SQL persistence against isolated SQLite engines without replacing module globals.
- `WorkflowStateRepository` accepts an injected reset-event emitter, replacing the prior module-level monkeypatch path in the persistence test.

The implementation deliberately does not add `aeat app modelo resume` and does not start a modelo filing lifecycle attempt. The apex plan assigns the public CLI resume verb and modelo-level idempotency/file orchestration to W80.

Rows checked in the plan:

- `S1741` service ownership mapped to `aeat.application.workflow`
- `S1742` command/result contracts implemented
- `S1743` workflow resume service wiring completed for terminal run loading and context assembly
- `S1744` secure workflow-run persistence integration covered
- `S1745` existing workflow-run loading routed through the canonical resume service
- `S1746` resume error/log fields recorded
- `S1759` service contract tests added/updated
- `S1760` persistence integration tests added/updated
- `S1764` targeted workflow test slice run

Rows intentionally left open:

- W59 CLI exposure and CLI behavior rows remain open because W80 owns `aeat app modelo resume`.
- W59 boundary-inventory rows remain open until the W80 CLI/modelo surface lands.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/workflow/test_resume.py src/aeat/application/workflow/test_models.py src/aeat/application/workflow/test_persistence.py`
- `uv run --no-sync ruff check src/aeat/application/workflow/_models.py src/aeat/application/workflow/_engine.py src/aeat/application/workflow/_persistence.py src/aeat/application/workflow/_resume.py src/aeat/application/workflow/__init__.py src/aeat/application/workflow/test_resume.py src/aeat/application/workflow/test_persistence.py src/aeat/application/workflow/test_models.py`

Wider workflow verification passed:

- `uv run --no-sync pytest -q src/aeat/application/workflow`
- `uv run --no-sync ruff check src/aeat/application/workflow`

Code-review remediation:

- Scoped review found that invalid `resumed_from` values were rejected only when the final `WorkflowResult` was constructed, after workflow stages had already run. The engine now validates `resumed_from` at the public `run_for_period` boundary, and `test_run_for_period_rejects_invalid_resume_link_before_stages` proves preflight is not reached.
