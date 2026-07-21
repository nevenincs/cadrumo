---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S21'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Replace LLM telemetry test-export imports with real adapter sources

## Scope

- `src/aeat/application/ledger/tests/test_llm_classify_run_telemetry.py`
- `src/aeat/application/tests/test_diagnostics_telemetry.py`

## Description

- Grounded the cleanup with `uvx vaultspec-rag search "application_adapter_exports remaining direct source imports ledger evidence LLM telemetry real adapter" --type code`.
- Confirmed `LLMRunRecord` and `LLMRunTelemetryRecorder` are exported by the real `src/aeat/adapters/outbound/llm` adapter facade and defined in its run-telemetry module.
- Confirmed `TransactionCatalogueRepository` is defined in `src/aeat/adapters/persistence/profile/transactions.py`.
- Replaced imports from `src/aeat/tests/application_adapter_exports.py` with direct imports from the real adapter sources.

## Outcome

The LLM run telemetry tests now provision local-only telemetry records/recorders and the transaction repository from their real adapter sources. This keeps the diagnostic and ledger-classification test surfaces aligned with the no-reexport campaign constraint.

Focused gates passed:

- `uv run --no-sync ruff check src/aeat/application/ledger/tests/test_llm_classify_run_telemetry.py src/aeat/application/tests/test_diagnostics_telemetry.py` - passed.
- `uv run --no-sync pytest -q src/aeat/application/ledger/tests/test_llm_classify_run_telemetry.py src/aeat/application/tests/test_diagnostics_telemetry.py -n 0` - `9 passed`.

## Notes

No production code changed. The tests still exercise real subprocess classification, encrypted local telemetry persistence, and the loopback HTTP telemetry flush path.
