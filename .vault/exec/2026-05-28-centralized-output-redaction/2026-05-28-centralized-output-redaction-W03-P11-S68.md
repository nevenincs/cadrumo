---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S68'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---




# update error-registry contract tests for shared context redaction behavior

## Scope

- `src/aeat/entrypoints/cli/test_error_registry_contract.py`

## Description

- Validate error-registry contract tests for shared context redaction behavior.
- Remove the `N818` suppression from the Modelo IVA wallet blocked exception by introducing the canonical `ModeloIvaWalletReconciliationBlockedError` class and registering that class path.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/entrypoints/cli/test_windows_encoding.py` passed: 13 passed.
- `uv run pytest -q src/aeat/application/modelo/test_iva_wallet_decision_binding.py` passed: 9 passed.

## Notes

- `ModeloIvaWalletReconciliationBlocked` remains a public compatibility alias to the canonical `ModeloIvaWalletReconciliationBlockedError`; instantiated exceptions use the canonical class for registry lookup.
