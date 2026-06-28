---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S65'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# live-iva-compensation-wallet W07.P18.S65

Scope: Modelo readiness and workflow-facing blocking for IVA wallet divergence states.

## Description

- Audit current Modelo readiness tests for blocked, stale, missing-wallet, filed-history-only, and override-required IVA compensation decisions.
- Verify localized IVA wallet blocking message and next-action helpers render operator-facing guidance.
- Verify persisted filed-history-only decisions block verification readiness and export before file emission.
- Verify real Modelo 303 calculation blocks wallet-lower, wallet-stale, and missing-evidence decisions.
- Verify explicit taxpayer override unblocks the real Modelo 303 engine when filed-history fallback evidence is reviewed.

## Outcome

S65 is satisfied by current implementation and tests. Blocked IVA wallet decisions surface as readiness findings before verification/export/file workflow progress, and explicit taxpayer overrides remain the non-blocking review path.

Verification passed:

- `python -m pytest -q src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocking_finding_next_action_is_localised src/aeat/application/modelo/test_actions.py::test_iva_wallet_blocked_message_is_localised src/aeat/application/modelo/test_export.py::test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only src/aeat/application/modelo/test_export.py::test_verify_modelo_303_surfaces_filed_history_only_wallet_decision_as_blocking_readiness src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_wallet_lower_divergence_blocks_real_modelo_303_engine_before_persisting_revision src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_stale_wallet_divergence_blocks_real_modelo_303_engine_before_persisting_revision src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_missing_remote_and_local_compensation_blocks_real_modelo_303_engine src/aeat/application/modelo/test_iva_wallet_engine_integration.py::test_missing_wallet_requires_explicit_override_before_real_modelo_303_engine_prefill`
- `python -m ruff check src/aeat/application/modelo/test_actions.py src/aeat/application/modelo/test_export.py src/aeat/application/modelo/test_iva_wallet_engine_integration.py`

## Notes

No code change was required for this step. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
