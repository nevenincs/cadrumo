---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S1531-S1533-S1535-S1536-S1549-S1554'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
---

# `cli-workflow-redesign` `W52.P256` service contract slice

Completed the first backend-owned per-modelo aggregation service slice.

- Added: `src/aeat/application/aggregation/_service.py`
- Added: `src/aeat/application/aggregation/test_per_modelo_service.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

Baseline verification found W52 fully open in the plan even though later W84 aggregation family work had already delivered retenciones, 347/349 counterpart, and 720 pure aggregators. The missing W52 backend piece was a centralized, non-CLI application service contract that owned provider mapping, command/result schemas, logging fields, and error-code metadata.

The new `aeat.application.aggregation._service` module adds strict frozen Pydantic contracts:

- `PerModeloAggregationCommand`
- `PerModeloAggregationResult`
- `PerModeloAggregationContract`
- `PerModeloAggregationProviderContract`
- `PerModeloAggregationLogFields`

`aggregate_per_modelo` now routes supported modelos through the real implemented aggregators:

- 111, 115, 123, 180, 190, 193 -> retenciones providers
- 347, 349 -> counterpart providers
- 720 -> foreign-assets provider

The service enforces the four accepted source kinds through the existing observation models and its backend contract, rejects cross-family observation payloads, exposes stable non-secret log fields, and records the registered aggregation error codes. It has no CLI dependency and does not introduce compatibility shims.

Post-review remediation added strict modelo dispatch coherence: non-canonical whitespace modelo values are refused before dispatch, and `PerModeloAggregationResult` validates that its aggregation payload matches the envelope modelo, period, and provider.

Rows checked in the plan:

- `S1531` service ownership mapped to `aeat.application.aggregation`
- `S1532` Pydantic command/result contracts implemented
- `S1533` existing aggregation services wired through the central dispatcher
- `S1535` standalone backend functions routed behind the canonical service boundary
- `S1536` service log fields and error-code metadata recorded
- `S1549` service contract tests added
- `S1554` targeted aggregation test slice run

Rows intentionally left open:

- `S1534` / `S1550`: no fake persistence/provider bridge was added for retenciones, counterpart, or 720; repository integration remains a concrete follow-up.
- `S1537` through `S1548`: duplicate/shim audit and removal requires a separate pass.
- `S1551` through `S1553` and `S1555` through `S1560`: CLI exposure and command-level tests remain future thin-adapter work.

## Tests

Focused verification passed:

- `uv run --no-sync pytest -q src/aeat/application/aggregation/test_per_modelo_service.py` passed 8 tests
- Post-review rerun: `uv run --no-sync pytest -q src/aeat/application/aggregation/test_per_modelo_service.py` passed 11 tests
- `uv run --no-sync pytest -q src/aeat/application/aggregation src/aeat/application/modelo/test_bucket_aggregation_flow.py` passed 183 tests
- `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation` collected 179 tests
- `uv run --no-sync ruff check src/aeat/application/aggregation/_service.py src/aeat/application/aggregation/test_per_modelo_service.py src/aeat/application/aggregation/__init__.py`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`

Review record:

- `.vault/audit/2026-05-14-cli-workflow-redesign-W52-service-review.md`
