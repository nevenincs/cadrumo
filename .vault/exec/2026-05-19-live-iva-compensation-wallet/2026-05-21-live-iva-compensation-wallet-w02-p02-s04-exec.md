---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P02.S04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W02.P02.S04`

Added regression coverage so unclassified live AEAT form/query actions fail before browser dispatch.

- Modified: `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- Modified: `src/aeat/adapters/outbound/aeat/verify/test_verify.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_groi_check.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py`
- Modified: registry guard/oracle tests
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

The test surface now proves unclassified browser actions are blocked for:

- Wallet read guard.
- Declarations read guard.
- CSV verification read guard.
- Registry guard allow-list behavior and wildcard behavior.
- GROI oracle and direct GROI live driver.
- NIF-IVA oracle and direct NIF-IVA live driver.
- Renta WEB Open oracle/simulator action planning.

Existing Renta WEB Open source-level safety tests continue to enforce that every driver click flows through `assert_click_target_safe` before Playwright dispatch. Wallet tests continue to prove wallet POST/execute submission is rejected and no-table wallet shells cannot become false zero-wallet observations.

`uv run vaultspec-core vault plan step check` was attempted for `S04`, but this L3 plan contains duplicate leaf ids and the CLI closed a different `S04` row. The exact `W02.P02.S04` display-path row was therefore updated directly after verification with `uv run vaultspec-core vault plan query --wave W02 --open`.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_groi_check.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py src/aeat/domain/calculations/registry/test_remote_state_guard.py::test_oracle_bound_cross_reference_policy_gets_consult_action_allow_list -q --disable-warnings` passed with 109 tests.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_groi_check.py src/aeat/adapters/outbound/aeat/sede/test_groi_check.py src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py` passed.
