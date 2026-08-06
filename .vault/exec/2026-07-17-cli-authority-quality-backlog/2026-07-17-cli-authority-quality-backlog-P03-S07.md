---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:7047dc74b65e103d54444d691b228e63defd83b335f767d2456f07697a6dedb9'
step_id: 'S07'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Remove duplicate namespace, version, sensitivity, catalogue-key, and custody literals from transaction, invoice, modelo participation, and bucket persistence consumers and bind them to registry definitions

## Scope

- `src/cadrumo/domain/transactions/`

## Description

- Identify the transaction-catalogue namespace duplication: the domain port `_repository.py` declared raw literals `TX_BUCKET_NAMESPACE = "cadrumo.domain.transactions.bucket"` and `_TX_CATALOGUE_VERSION = 1`, duplicating the registry authority `TRANSACTION_CATALOGUE_NAMESPACE`.
- Confirm the binding cannot flow through the domain: the `domain-not-adapters` import-linter contract forbids a production domain-to-adapters edge, so persistence-namespace metadata cannot be bound to the registry from inside the domain — it must leave the domain.
- Delete both domain literals and drop `TX_BUCKET_NAMESPACE` from the domain `transactions` `__all__` and lazy-export surface; the pure port keeps only `ImportSummary` and the two key-derivation helpers.
- Rewire the two production consumers (`application.ledger._actions_common`, `application.ledger._actions_import`) and the aggregation ledger-mesh test to read `TRANSACTION_CATALOGUE_NAMESPACE.namespace` from the storage facade.

## Outcome

- Behaviour-preserving: the namespace string is byte-identical (`cadrumo.domain.transactions.bucket`), now single-sourced at the registry; the adapter's own registry-bound `TX_BUCKET_NAMESPACE` alias is untouched.
- Green: `domain-not-adapters` and `Domain must not import application` import-linter contracts KEPT; `collect-only` clean (970/976, 6 deselected); focused suites pass (domain transactions + adapter roundtrip + aggregation ledger mesh = 159; application ledger = 386); `ruff`, `ty`, docstring core-struct-links all green.
- Both ledger consumer modules were already pinned `application.ledger._actions_* -> cadrumo.adapters.**` in the layered contract, so no new architecture edge was introduced.
- Committed as `86043bfc12` (five files, tagged `relocation:TX_BUCKET_NAMESPACE`).

## Notes

- The plan text "bind them to registry definitions" for `domain/transactions/` was architecturally impossible as literally stated because of `domain-not-adapters`; the layering-correct realization is that persistence metadata leaves the domain entirely and its (application-layer) consumers bind to the registry. The ADR already pre-decided the registry as the sole authority, so the domain literal was definitionally the duplicate.
- One pre-existing repo-wide layered-contract breakage (`application.live._filed_capture_finalizer -> adapters.outbound.aeat.sede`) is committed peer P04 work, not this step's surface; left for the owning campaign.
- The step's plan text also names invoice / modelo-participation / bucket persistence consumers; the transaction-catalogue namespace was the concrete duplicate found under `domain/transactions/`. No further raw namespace/version/sensitivity/custody literals remained in that package after this change.
