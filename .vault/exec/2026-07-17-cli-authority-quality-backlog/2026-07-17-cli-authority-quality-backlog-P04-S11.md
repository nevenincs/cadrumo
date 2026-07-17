---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S11'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---




# Make filed observation persistence the sole owner of latest-record selection, deterministic history ordering, metadata enrollment, and calculation-observation writes and remove the duplicate selector and persistence loop from capture orchestration

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Extract `select_latest_filed_observations_in_history_order` into `_filed_observation_persistence.py` as the single latest-selection + history-ordering authority (latest by `_filed_observation_rank` — ALTA over BAJA, then presented_at, then expediente_id; ordered by `_filed_observation_history_period_sort_key` — Modelo 303 IVA fiscal order, numeric elsewhere), and add it to `__all__`.
- Refactor `persist_latest_filed_calculation_observations` to consume that shared selector rather than reimplementing the selection/ordering inline.
- Remove the duplicate selector + persistence loop from capture orchestration: delete `_persist_latest_filed_calculation_observations_with_failures`, `_filed_registry_enrollment_failure_row`, and `_raise_registry_enrollment_failure` from `_filed_data_capture.py`, and route all three capture routes (single, bulk, source) through the new `finalize_filed_capture` finalizer instead.
- Drop the now-unused `_filed_observation_rank`, `persist_filed_calculation_observation`, `SedeParseError`, and `LiveApplicationError` imports from the capture module.

## Outcome

Filed-observation persistence is now the sole owner of latest-record selection, deterministic history ordering, metadata enrollment, and calculation-observation writes. The capture module previously reimplemented selection with a DIVERGENT ordering key (raw `registry_token` vs the authority's fiscal/numeric history-period key); both now share one function, so the capture-path and the calculation-history path cannot drift. Full application/live suite: 185 passed; ruff clean.

## Notes

git-diff-gated all application/live files clean at HEAD before editing (team lead reserved P04 for me vs exec-dist-identity). The finalizer that the capture routes now call is authored under S12; the shared-selection/ordering/distinct-policy proof is S13.
