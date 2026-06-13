---
tags:
  - '#audit'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
---

# `live-iva-compensation-wallet` code review

Review scope: offline implementation slice for the live IVA compensation wallet
plan, including external constants, wallet evidence schemas, wallet parser and
read-only driver, encrypted wallet evidence persistence, reconciliation decision
persistence, Modelo 303 decision consumption, and focused tests.

## Findings

- [x] `MEDIUM` - Bucket aggregation calculation path did not forward the IVA
  wallet reconciliation decision into `calculate_modelo_revision`. This would
  allow the repository-driven calculation path to bypass the new Modelo 303
  wallet guard. Fixed by adding `iva_compensation_decision` to
  `calculate_modelo_revision_from_bucket_aggregation` and forwarding it to the
  core calculation action.

- [ ] `LOW` - The live Cl@ve smoke test and workflow command entry point remain
  open by plan. This is intentional for this slice because no authenticated AEAT
  session was started and the operator-approved command surface still needs to
  be added before live manual approval is requested.

- [ ] `LOW` - The wallet parser is tested with an offline fixture matching the
  expected AEAT table labels. A future live capture should be saved as a
  redacted fixture after operator-approved access confirms the exact DOM.

## Verification

Focused verification passed:

`uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py src/aeat/application/calculations/test_iva_wallet_reconciliation.py src/aeat/application/calculations/test_observations_repository_roundtrip.py src/aeat/application/modelo/test_iva_wallet_decision_binding.py src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_relation_offset.py src/aeat/domain/calculations/registry/test_modelo_chain_resolution.py -q`

Result: `95 passed`.
