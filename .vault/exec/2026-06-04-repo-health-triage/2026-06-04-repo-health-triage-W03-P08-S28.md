---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P08.S28'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P08.S28 - Extract modelo IVA wallet gate service

Scope: execute the modelo application orchestration decomposition step for Modelo 303 IVA wallet reconciliation gates.

## Description

- Add `_iva_wallet_gate.py` as the application-layer IVA wallet gate service.
- Move Modelo 303 prior-compensation decision resolution, binding application, persisted-decision replay checks, blocked-message rendering, and taxpayer NIF lookup behind the new service.
- Preserve the existing `_actions.py` private import surface used by export, CLI, and focused tests.
- Update the domain error registry entry to point at the moved exception class.

## Outcome

- `_actions.py` no longer owns the IVA wallet helper bodies; it delegates to `_iva_wallet_gate.py` through compatibility aliases.
- `_iva_wallet_gate.py` owns the current exception behavior, including the concurrent translated-message metadata for wallet mismatch paths.
- Existing export, verification, and binding callers continue to import the historical private names from `_actions.py`.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_iva_wallet_gate.py src/aeat/core/errors/registry/_domain.py`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_iva_wallet_decision_binding.py -q`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocked_message_is_localised src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocked_exception_carries_translated_message_key src/aeat/test_w20_p52_closure.py::test_s643_iva_wallet_decision_token_present -q`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_export.py::test_export_refuses_modelo_303_when_persisted_wallet_decision_is_blocked src/aeat/application/modelo/test_export.py::test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only -q`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_iva_wallet_engine_integration.py -q`
- The initial export verification command used stale test node ids and collected no tests; the corrected node ids above passed.
