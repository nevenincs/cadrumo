---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P02.S03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W02.P02.S03`

Moved accepted live AEAT action markers into external constants and guard policies.

- Modified: `src/aeat/core/external_constants.toml`
- Modified: `src/aeat/core/external_constants.py`
- Modified: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Modified: wallet, declarations, CSV verifier, GROI/NIF-IVA, and Renta WEB Open policy/test surfaces
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

Accepted browser-action labels now live under `aeat.live_safety` in the external constants registry. The remote-state guard supports `allowed_browser_action_patterns`, including wildcard-reviewed labels such as `check-nif-*`, `navigate-to-casilla:*`, and `scrape-summary-field:*`.

The following surfaces consume these centralized patterns:

- Wallet selector dispatch through the wallet read policy.
- Filed declarations register clicks and snapshot-derived declarations read policies.
- CSV verification query entry.
- GROI/NIF-IVA oracle-bound registry policies.
- Direct GROI/NIF-IVA live driver query guards.
- Renta WEB Open oracle policies and planned simulator actions.

`uv run vaultspec-core vault plan step check` was attempted for `S03`, but this L3 plan contains duplicate leaf ids and the CLI closed a different `S03` row. The exact `W02.P02.S03` display-path row was therefore updated directly after verification with `uv run vaultspec-core vault plan query --wave W02 --open`.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_groi_check.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py src/aeat/domain/calculations/registry/test_remote_state_guard.py::test_oracle_bound_cross_reference_policy_gets_consult_action_allow_list -q --disable-warnings` passed with 109 tests.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_groi_check.py src/aeat/adapters/outbound/aeat/sede/test_groi_check.py src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py src/aeat/adapters/outbound/aeat/sede/test_nif_iva_check.py src/aeat/domain/calculations/registry/_remote_state_guard.py src/aeat/domain/calculations/registry/test_groi_oracle.py src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py` passed.
