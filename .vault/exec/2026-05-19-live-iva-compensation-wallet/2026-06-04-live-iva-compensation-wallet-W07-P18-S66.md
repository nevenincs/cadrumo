---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S66'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W07.P18.S66

Scope: non-private divergence-state coverage for IVA wallet reconciliation and Modelo 303 engine consumption.

## Description

- Audit the current `IvaCompensationDivergence` vocabulary against direct reconciliation tests.
- Add explicit real Modelo 303 engine and lifecycle coverage for non-blocking `first_period_zero`.
- Verify the production reconciliation matrix, Modelo 303 engine blocking paths, export refusal paths, and localized readiness helpers with active test ids.
- Record the failed broad gate selector as a command-selection failure, not a code failure.

## Outcome

S66 now covers every divergence state with synthetic wallet/filed-history/local evidence and production code paths. Direct reconciliation covers the closed divergence vocabulary, while Modelo 303 integration now proves `first_period_zero` can feed calculation and pass the lifecycle authority gate without private taxpayer fixtures. Blocked divergence states remain covered through the real calculation/export/readiness boundaries.

Verification passed:

- `python -m pytest -q src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_first_period_zero_decision_feeds_real_modelo_303_engine_and_lifecycle_gate src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_no_seed_no_override_303_calculate_lazily_reconciles_local_zero_and_surfaces_casilla_110 src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_wallet_only_decision_feeds_real_modelo_303_engine_and_lifecycle_gate src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_wallet_lower_divergence_blocks_real_modelo_303_engine_before_persisting_revision src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_stale_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_missing_remote_and_local_compensation_blocks_real_modelo_303_engine`
- `python -m pytest -q src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/modelo/test_export.py::test_export_refuses_modelo_303_when_persisted_wallet_decision_is_blocked src/aeat/application/modelo/test_export.py::test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only src/aeat/application/modelo/test_export.py::test_verify_modelo_303_surfaces_filed_history_only_wallet_decision_as_blocking_readiness src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocking_finding_next_action_is_localised src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocked_message_is_localised`
- `python -m ruff check src/aeat/application/modelo/test_iva_wallet_engine_integration.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_actions.py`

## Notes

One attempted broader pytest command failed before executing tests because the selected export test id had drifted. The corrected active test id was used in the passing broader gate. The code-review pass also narrowed the new test away from a final-result arithmetic assertion and kept it on the wallet binding, casilla, and lifecycle contract. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
