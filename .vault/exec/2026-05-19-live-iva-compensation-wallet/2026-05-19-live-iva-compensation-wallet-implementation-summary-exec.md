---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-code-review-audit]]'
---

# `live-iva-compensation-wallet` `implementation` summary

Implemented the offline and read-only backend slice for the AEAT IVA
compensation wallet.

- Modified: `src/aeat/core/external_constants.toml`
- Modified: `src/aeat/core/external_constants.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_schema.py`
- Created: `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`
- Created: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`
- Modified: `src/aeat/application/calculations/_observations_repository.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`

## Description

The implementation adds the AEAT wallet endpoint constant, strict read-only
wallet evidence records, an authenticated Sede wallet reader, an offline parser,
encrypted wallet evidence persistence, encrypted reconciliation decision
persistence, and a deterministic reconciliation decision model.

Modelo 303 calculation now accepts an IVA compensation reconciliation decision.
A non-blocking decision supplies the prior compensation binding. A blocked
decision or conflicting caller binding refuses automatic calculation.

No live AEAT login was started. The Cl@ve-backed run remains an operator-approved
future execution step once the workflow or CLI command surface is added.

## Tests

Focused verification passed:

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_relation_offset.py src/aeat/domain/calculations/registry/test_modelo_chain_resolution.py -q`

Result: `95 passed`.
