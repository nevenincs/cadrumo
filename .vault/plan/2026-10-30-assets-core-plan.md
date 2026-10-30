---
tags:
  - '#plan'
  - '#assets-core'
date: '2026-10-30'
tier: L1
related:
  - '[[2026-08-23-amortization-casilla-mapping-adr]]'
  - '[[2026-09-21-assets-core-lifecycle-contract-adr]]'
  - '[[2026-09-23-assets-core-amortization-method-set-adr]]'
  - '[[2026-09-23-assets-core-vehicle-affectation-adr]]'
  - '[[2026-09-21-assets-core-cost-basis-stages-adr]]'
  - '[[2026-10-30-assets-core-amortization-law-and-form-placement-research]]'
  - '[[2026-10-30-assets-core-implementation-state-against-law-reference]]'
modified: '2026-10-30'
body_schema: body-v2
body_hash: 'sha256:12308d307775a7ac1570b9334a715a0cf40ef7699207d1b11af989b6b77730c1'
---

<!-- RETIRED: S02, S03 -->

# `assets-core` plan

## Description

Approved 2026-10-30. Basis: the operator's direct instruction that this session and CADRUMO-AMPORTIZATION1 implement the backend and ensure it is fully capable, including ADRs, facts, adding and removing assets, amortization plans, table verification and correct calculation, and that amortization is not a blocker.

Backend for the ledger's inmovilizado and amortization. Frontends follow separately and are out of this plan, apart from the operations they consume. Decision coverage: the 2026-10-30 amendments of the linked ADRs govern every Step except disposal, which has no decision yet, so S10 records it and S11 executes on it. Legal rulings are in `2026-10-30-assets-core-amortization-law-and-form-placement-research`, section Rulings for implementation.

Owners: CADRUMO-AMORTIZATION2 has S01, S05, S06, S08, S09, S12. CADRUMO-AMPORTIZATION1 has S04, S07, S10, S11, S13. S14 is run last by an independent reviewer.

## Steps

- [x] `S01` - Compute charges as the difference of the rounded cumulative charge of the tax year, so contiguous intervals sum to the annual figure; `src/cadrumo/domain/renta/actividad_asset/schedule.py`.
- [ ] `S04` - Verify the amortization tables and facts against the law for every supported year, normal LIS art. 12.1.a and simplified Orden 27-03-1998, correcting any out-of-date parameter or fact, with an independent table test; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/, src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py`.
- [x] `S05` - Remove the unused claim revision fields, define one effective-claim selection and a pure gap finder, and refuse a correction whose basis is below effective claims; `src/cadrumo/domain/renta/actividad_asset/claims.py, src/cadrumo/application/actividad_asset/history.py`.
- [ ] `S06` - Add the non-deductible IVA acquisition component to the basis, the EUR 300 valor unitario test, the later afectacion base and the acquisition transaction check; `src/cadrumo/domain/renta/actividad_asset/lifecycle.py, election.py, src/cadrumo/application/actividad_asset/operations.py`.
- [ ] `S07` - Author the 0227 binding from 2022, remove the amortizable ledger categories from 0208 routing and retire their low-value and home-ratio deductions; `src/cadrumo/_data/registry/aeat/modelos/100/revisions/, src/cadrumo/_data/registry/aeat/facts/, src/cadrumo/domain/renta/ledger_expenses.py`.
- [ ] `S08` - Route Modelo 100 from effective claims with non-blocking gap findings, compute Modelo 130 casilla 02 accrual from the schedule excluding agrarian activities, make the collision unconditional, refuse foral residents and type the history load failure; `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py, modelo_bindings_renta_expenses.py, src/cadrumo/application/modelo/calculation_notes.py`.
- [ ] `S09` - Record consumed claim IDs and schedule fingerprints on the calculation revision and mark a change as staleness in the drift gate; `src/cadrumo/domain/modelos/calculation_revision.py, src/cadrumo/application/modelo/_ledger_drift_gate.py`.
- [x] `S10` - Record and accept the disposal decision covering transmission, baja with zero proceeds, minimum amortization, DA 30 and DA 59 excess, and casillas 0179, 0387, 1846 and 1478; `.vault/adr/`.
- [ ] `S11` - Implement baja of an element with date and reason and its disposal calculation through registered operations, so an element leaves the register without erasing history; `src/cadrumo/domain/renta/actividad_asset/, src/cadrumo/application/actividad_asset/`.
- [ ] `S12` - Add the read model and operations: element list, per-year amortization plan with typed claim state, claimable intervals and authored or projected edition, ordered event timeline with sequence and nullable recorded time, claim used_by and schedule match, form options, acquisition candidates, refusal sub-reason keys, atomic correction with superseding claims, earlier-year claiming for rate methods, and a non-tax descriptor record for name, serial number and libro registro fields outside revision identity via ledger.actividad-asset.describe; `src/cadrumo/application/actividad_asset/, src/cadrumo/domain/renta/actividad_asset/claims.py and operation registration`.
- [ ] `S13` - Prove the calculations end to end with the official worked-example oracles, a used-asset case from RIS art. 4.3, and the invariants that quarterly accrual sums to the annual charge and Modelo 130 Q4 equals 0208 plus 0227 when claims are complete; `owning tests directories`.
- [ ] `S14` - Run the integrated review across the amended decisions and the backend, and append findings to the rolling audit; `.vault/audit/`.
- [ ] `S15` - Localize every activity-asset refusal through registered catalogue keys in en, es, ca and hu, with a gate rejecting literal messages in the package, authorized by the operator's 2026-10-30 instruction that surfaced refusals must be translated; `src/cadrumo/domain/renta/actividad_asset/, src/cadrumo/application/actividad_asset/, src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py, src/cadrumo/locales/`.

## Parallelization

Two sessions share the `tui` worktree, so write ownership is disjoint and commits use explicit paths. CADRUMO-AMORTIZATION2 owns the calculation path: schedule, claims, basis, aggregation, staleness, read model. CADRUMO-AMPORTIZATION1 owns the legal and registry work: table verification, registry routing and ledger retirement, the disposal decision and implementation, and the oracles. Schedule rounding comes first. Registry routing and aggregation land together because retiring the routes without the gap findings would drop deductions silently, so those two owners coordinate that commit. Disposal follows claims. The review runs last on a stable set.

## Verification

An element can be added, corrected, amortized by recorded claims and given a baja through the registered operations, and its amortization plan, per-year amounts and pending value can be read. Official worked examples pass as independent oracles through the real resolver. Tables match their legal sources for every supported year. No ledger category reaches 0208 or 0227. A missing claim yields a non-blocking finding and never a refusal. Focused tests, import boundaries, style, format and types pass for touched code, and the integrated review passes.
