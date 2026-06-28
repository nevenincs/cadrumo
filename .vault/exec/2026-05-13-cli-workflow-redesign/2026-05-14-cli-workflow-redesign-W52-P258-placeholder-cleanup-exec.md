---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S1543-S1544-S1545-S1547-S1548'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
---

# `cli-workflow-redesign` `W52.P258` placeholder cleanup slice

Removed the remaining per-modelo aggregation placeholder unsupported-modelo paths from the scoped aggregation implementation.

- Modified: `src/aeat/application/aggregation/_retenciones.py`
- Modified: `src/aeat/application/aggregation/_counterpart.py`
- Modified: `src/aeat/application/aggregation/test_retenciones.py`
- Modified: `src/aeat/application/aggregation/test_counterpart.py`
- Modified: `src/aeat/entrypoints/cli/test_backend_boundary.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

The previous retenciones and counterpart private filtering helpers raised `NotImplementedError` for unsupported modelos, and their tests asserted that placeholder behavior. Those paths now raise the registered `AggregationUnsupportedModeloError` with concrete allowed-model suggestions and central error-code registration. The implementation no longer contains `NotImplementedError` or "not implemented" placeholder wording in the scoped aggregation files.

The CLI/backend boundary inventory now records that these per-modelo aggregation placeholder paths must stay removed.

Rows checked in the plan:

- `S1543` compatibility placeholder path removed
- `S1544` placeholder stubs removed
- `S1545` placeholder paths replaced by the real `aggregate_per_modelo` backend service call boundary
- `S1547` tests asserting placeholder behavior replaced
- `S1548` boundary inventory guard added

Rows intentionally left open:

- `S1546`: deprecated command spelling and help text is CLI adapter work.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_retenciones.py src/aeat/application/aggregation/test_counterpart.py src/aeat/application/aggregation/test_per_modelo_service.py` passed 60 tests
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_backend_boundary.py::test_per_modelo_aggregation_placeholder_paths_stay_removed src/aeat/application/aggregation/test_retenciones.py::TestAggregate111::test_unknown_modelo_uses_registered_aggregation_error src/aeat/application/aggregation/test_counterpart.py::TestInvariants::test_unknown_modelo_uses_registered_aggregation_error` passed 3 tests
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/application/aggregation/_retenciones.py src/aeat/application/aggregation/_counterpart.py src/aeat/application/aggregation/test_retenciones.py src/aeat/application/aggregation/test_counterpart.py`
- Read-only baseline for `S1545` confirmed no surviving stub or placeholder path in `src/aeat/application/aggregation` and verified the real `aggregate_per_modelo` service dispatch boundary.
