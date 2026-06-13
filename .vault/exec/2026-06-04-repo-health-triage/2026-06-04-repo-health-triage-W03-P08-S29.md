---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P08.S29'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P08.S29 - Extract modelo revision-persistence service

Scope: execute the modelo application orchestration decomposition step for calculation-revision persistence and filing-state transitions.

## Description

- Add `_revision_persistence.py` as the application-layer persistence helper for modelo revision mutations.
- Move bucket-event emission out of `_actions.py` while preserving the private `_emit_bucket_event` call surface.
- Move draft calculation-revision persistence, work-unit current-revision advancement, and `modelo.calculation.created` event emission behind `persist_calculation_revision`.
- Move verified-complete filing persistence, filing supersession, filed-revision state transitions, work-unit filing pointers, and filed/superseded event emission behind `persist_filed_revision`.

## Outcome

- `_actions.py` keeps validation, workflow gates, and registry calculation orchestration; `_revision_persistence.py` owns the mutation-heavy catalogue writes for calculate/file flows.
- The calculate path continues to deduplicate identical content-addressed revisions before mutation.
- The file path continues to refuse before mutation when workflow or IVA wallet replay gates block, then delegates the successful transition atomically through the new helper.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_revision_persistence.py src/aeat/application/modelo/test_file_flow.py src/aeat/application/modelo/test_export.py`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_file_flow.py -q`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_export.py::test_file_modelo_303_uses_injected_wallet_decision_repository_before_mutation src/aeat/application/modelo/test_export.py::test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only -q`
