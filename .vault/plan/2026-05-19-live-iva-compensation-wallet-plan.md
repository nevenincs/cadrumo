---
tags:
  - '#plan'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
tier: L3
related:
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
---

# `live-iva-compensation-wallet` `implementation` plan

Implement the AEAT-held IVA compensation wallet as the primary read authority
for Modelo 303 prior compensation, with local recurrence retained as
reconciliation and fallback evidence.

## Proposed Changes

The implementation adds a read-only Sede driver for AEAT's `Cartera de Cuotas a
Compensar`, persists wallet observations with raw evidence provenance, and adds
an application-level reconciliation layer. Modelo 303 prefill does not read the
live adapter directly. It consumes a persisted reconciliation decision with a
strict authority ladder: live wallet first, explicit taxpayer override second,
local filed-declaration reconstruction third. Divergence between AEAT wallet
state and local recurrence produces a review-blocking reconciliation outcome
rather than a silent calculation choice.

The Vaultspec plan CLI was unavailable in this environment, so this document is
authored directly from the repository template with stable identifiers.

## Steps

## Wave `W01` - live wallet read authority

This Wave builds the live AEAT read path and makes it the primary authority for
the Modelo 303 prior compensation binding. It must precede treating the IVA
calculation chain as production-complete.

### Phase `W01.P01` - declare read-only wallet surface and state records

This Phase records AEAT's wallet endpoint, strict read-only evidence schema, and
the internal reconciliation decision record that calculation code will consume.

- [x] `W01.P01.S01` - add the wallet path and tests to the external constants registry; `src/aeat/core/external_constants.toml`.
- [x] `W01.P01.S02` - add strict wallet observation and row schemas; `src/aeat/adapters/outbound/aeat/sede/_schema.py`.
- [x] `W01.P01.S03` - add wallet reconciliation decision and divergence status records; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W01.P01.S04` - add wallet remote-operation guard policy and export surface; `src/aeat/adapters/outbound/aeat/sede/__init__.py`.

### Phase `W01.P02` - implement authenticated wallet capture

This Phase adds the Cl@ve/certificate-backed read driver and parser.

- [x] `W01.P02.S01` - implement `fetch_iva_compensation_wallet` as a read-only Sede adapter; `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py`.
- [x] `W01.P02.S02` - add parser coverage from captured wallet HTML fixtures; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py`.
- [ ] `W01.P02.S03` - add opt-in live smoke coverage gated by `AEAT_LIVE_TESTS_ENABLED`; `src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet_live.py`.

### Phase `W01.P03` - persist wallet evidence

This Phase stores wallet observations so calculation prefill can use the latest
authenticated AEAT evidence without requiring a live login on every calculation.

- [x] `W01.P03.S01` - add encrypted persistence support for wallet observations; `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`.
- [x] `W01.P03.S02` - add repository roundtrip tests for wallet observations; `src/aeat/adapters/outbound/aeat/sede/test_observation_store_roundtrip.py`.
- [x] `W01.P03.S03` - add encrypted persistence support for wallet reconciliation decisions; `src/aeat/application/calculations/_observations_repository.py`.
- [ ] `W01.P03.S04` - add CLI or workflow entry point for operator-approved wallet pull; `src/aeat/application/workflow/_engine.py`.

### Phase `W01.P04` - reconcile and prefill Modelo 303

This Phase connects wallet observations to the Modelo 303 prior compensation
binding and blocks silent divergence.

- [ ] `W01.P04.S01` - implement local recurrence extraction for comparison without selecting the effective value; `src/aeat/application/calculations/_binding_prefill.py`.
- [x] `W01.P04.S02` - implement wallet, override, local recurrence authority selection and blocking divergence statuses; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `W01.P04.S03` - consume only non-blocking reconciliation decisions for Modelo 303 prior compensation prefill; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S04` - prevent automatic output when the wallet reconciliation decision is blocked; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P04.S05` - add divergence scenario tests for match, AEAT-higher, AEAT-lower, stale wallet, missing wallet, and explicit taxpayer override; `src/aeat/application/calculations/test_iva_wallet_reconciliation.py`.
- [x] `W01.P04.S06` - run wallet, Modelo 303, Modelo 390, and relation-regression focused suites together; `tests`.

## Parallelization

`W01.P01` must land before the live driver because the endpoint, evidence
schema, and decision schema are the adapter and application contracts.
`W01.P02.S02` can develop parser fixtures in parallel with the driver.
`W01.P03` depends on the observation schema but can proceed before the
calculation prefill hook. `W01.P04` must run last because it consumes wallet
observations, local recurrence, explicit override metadata, and persisted
reconciliation decisions.

## Verification

The plan is complete when an operator can approve Cl@ve manually, pull the
read-only AEAT wallet, persist the wallet observation, create a persisted
reconciliation decision, prefill Modelo 303 casilla `110` only from a
non-blocking decision, compare the selected amount with local recurrence, and
produce a blocking reconciliation outcome for any material divergence unless an
explicit taxpayer override with provenance is recorded.
