---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:2f98b6d8360e84b70ae3172ee45aadf85e2c83a729ebd6321759d08869813d2d'
related:
  - "[[2026-10-30-assets-core-amortization-law-and-form-placement-research]]"
  - "[[2026-10-30-assets-core-implementation-state-against-law-reference]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-09-23-assets-core-amortization-method-set-adr]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
---

# `assets-core` adr: `Disposal of activity assets` | (**status:** `accepted`)

Accepted 2026-10-30 under the approved plan `2026-10-30-assets-core-plan`, Step S10, which authorizes recording and accepting this decision, and the operator's instruction of the same date to implement the law through the source hierarchy.

## Problem Statement

An element can leave the register only through `out_of_service_date` (`src/cadrumo/domain/renta/actividad_asset/lifecycle.py:291`), which bounds the charge window (`src/cadrumo/domain/renta/actividad_asset/schedule.py:359`) and nothing else. There is no reason, no proceeds, no cost reduction and no route to a form (`2026-10-30-assets-core-implementation-state-against-law-reference`). The lifecycle decision leaves disposal gain or loss to its own record. This is that record.

## Considerations

Settled law is in `2026-10-30-assets-core-amortization-law-and-form-placement-research`, section Rulings for implementation.

- A transmission gives a ganancia or pérdida patrimonial outside rendimiento neto (LIRPF art. 28.2), in the ahorro base (LIRPF art. 46.b; V0054-18, snippet).
- Minimum amortization reduces cost whether or not it was claimed (RIRPF art. 40.1 and 40.2). A skipped year stays within its own maximum. An ordinary amortization may be corrected locally for its own year within prescription.
- A libertad de amortización not taken cannot be taken later for that year, except within the regulatory filing period, and later years stay open (TEAC 01524/2017, an IS case under LGT art. 119.3, read in the CEF reproduction NFJ072523 because DYCTEA was unavailable; its application to IRPF is by analogy).
- Theft and destruction compute a ganancia or pérdida patrimonial with the indemnity as value of transmission and RIRPF art. 40 net value (V2285-14, V1161-19, both read in full for IRPF). V2285-14 places it in the general base under LIRPF art. 48.
- Scrapping is treated as a baja with zero proceeds by analogy: no consulta on scrapping was found.
- Only LIRPF DA 30.2 and DA 59.2 carve out excess, as rendimiento íntegro of the activity in the transmission period. LIS DA 17 has no carve-out; its workforce clawback sits in para. 7 and art. 102.4 serves art. 102, and neither is triggered by disposal.
- Residents of foral territories are refused.

## Considered options

- A disposal record on an append-only revision: keeps history and identity. Chosen.
- Keeping a free-standing `out_of_service_date` plus a separate disposal store: two sources for one date; rejected.
- Deleting the element at baja: erases evidence the libro registro and prior years need; rejected.
- Refusing a calculation with missing claims: contradicts RIRPF art. 40, which supplies the minimum; rejected.

## Constraints

Binding commitments: the record on an append-only revision, the boundary rule, the reduction and excess formulas, the route table, and the split between finding, blocking note and refusal. A missing claim is never a refusal. The outcome is local calculation only; nothing here submits to the tax agency. Refusals are registered and localized in every supported locale.

This amends the 2026-10-30 amendment of `2026-09-21-assets-core-lifecycle-contract-adr`, whose sentence leaving disposal open now points here.

## Implementation

We will record a baja as `ActivityAssetDisposal` on a superseding `ActivityAssetRevision`, and compute its result with one pure function.

**Record.** `disposal_date`; `reason` among `sale`, `part_exchange`, `theft`, `destruction`, `scrapping`, `withdrawal`; `proceeds`; `transmission_costs` (LIRPF art. 35.2); optional `market_value` (art. 35.2, second paragraph); optional attested `prior_free_depreciation_regime` for LIRPF DA 30.2; optional attested `later_affectation_on` for LIRPF art. 28.3, the date a later affectation began, which sets the route and changes no figure. `scrapping` requires zero proceeds, and a scrap sale is a `sale`. `theft` and `destruction` state any indemnity as proceeds. `withdrawal` means desafectación: it ends the charge window and computes no gain (LIRPF art. 28.3). Proceeds are stated for the whole element, except under a `business_allocated` basis. Donation is refused.

**Append-only.** Every other fact is copied unchanged and earlier revisions and claims stay in history. A mistaken baja is corrected by a further revision. `out_of_service_date` exists only as the record's derived boundary, and a free-standing date is refused. `revision_id` omits the field when absent, so existing identities do not change.

**Charge bound.** The disposal date is the last service day; the exclusive boundary is the next day. No source fixes this day: the manual example at part 1 lines 16043-16054 prorates by months and is ambiguous, so this is a chosen convention. Final-period charges remain the difference of the rounded cumulative charge, capped at the remaining base. Modelo 130 accrual stops at the boundary.

**Later claims.** A claim inside the window may still be recorded, including in the disposal year. A new positive claim ending past the boundary is refused. Effective claims crossing the boundary are superseded in the same compare-and-swap write as the baja: a crossing claim is shortened to the boundary and, if charged by time, recomputed; one wholly after it keeps its interval at amount zero. Shortening is the single exception to interval identity (`src/cadrumo/domain/renta/actividad_asset/claims.py:206-213`).

**Calculation**, in order:

- Acquisition value A: allocated price plus non-deductible IVA, including the land share of a property, which `deductible_basis` excludes (`src/cadrumo/domain/renta/actividad_asset/lifecycle.py:273-274`). Proceeds and costs of a whole-element statement take the same ownership and area or use shares.
- Deducted D: opening history plus effective claims, cumulatively.
- Minimum M: the amortizable base over the maximum period (`src/cadrumo/domain/calculations/registry/actividad_asset_bindings.py:393`), prorated by days and accumulated by year.
- Reduction R, year by year: R(y) = max(R(y-1) + claims(y), M through y), capped at the amortizable value. Years before the first effective claim form one opening span: max(opening, M over that span).
- Excess E, only for `electric_vehicle_free`, `charging_infrastructure_free` or an attested DA 30.2 regime: E = max(0, D - C), where C is the cumulative charge at the maximum table coefficient; then R = max(min(D, C), M). The statute does not define the counterfactual "hubieran sido fiscalmente deducibles"; the maximum coefficient follows the manual's example at part 1 line 16057 and is a supported reading, not a binding rule.
- Result = max(proceeds, market_value when stated) - costs - (A - R).

No minimum exists where no maximum period or fixed percentage does, including indefinite-life intangibles before 2016 (TEAC 10/02/2020, per the Renta 2025 manual, part 1). Those years count only what was deducted, with a finding.

**Routes.** Gain and loss never enter casilla 02 or rendimiento neto.

| Fact | Destination | Standing |
| --- | --- | --- |
| Gain on transmission, non-property | 1654 to 0387, ahorro | Research; formula exists |
| Gain on transmission, inmueble | 1843 to 1846, ahorro | Research; formula exists from 2022 |
| Loss on transmission, non-property | 1639 to 0385, ahorro | Direct: 2025 dictionary; no afecto split exists |
| Loss on transmission, inmueble | 1832 to 1844, ahorro | Direct: 2025 dictionary |
| Baja without transmission (theft, destruction, scrapping) | 0304 or 0305 to 0306 or 0307, general | Base direct in V2285-14; casilla derived from LIRPF arts. 45 and 46.b; scrapping by analogy |
| DA 30 or DA 59 excess, estimación directa | 0179 | DA 30 by label; DA 59 derived from the manual heading |
| DA 59 excess, módulos non-agrarian | 1478 | Derived from DA 59.2 and manual line 22058 |
| Excess in Modelo 130 casilla 01 | Quarter of the transmission, staying in later cumulative quarters | Derived from DA 59.2 and the casilla 01 instruction |
| DA 59 excess, módulos agrarian | Not established | No line found in `RegEstimaObjAgricola`; Orden HAC/1347/2024 Anexo I not obtained |
| Excess in Modelo 131 | Not established | Instructions silent |
| Clave 1626 on a gain or loss row | Not established | Design gives "0" to "7"; meanings not found |

The excess follows the determination method of the disposal year. This enrols no módulos amortization: estimación objetiva stays refused for elections and claims. Exemptions, operaciones a plazos and DT 9.ª rows are not produced; the full gain routes with a finding.

**Finding, blocking note or refusal.**

- Non-blocking finding: a missing claim or claim gap; a year where the minimum exceeded the deduction, with its effect on cost; a year with no minimum authority; exemption or deferral not computed; excess not routed to Modelo 131.
- Blocking calculation note, using the `unrouted_observation` mechanism, with the baja still recorded: any gain, loss or excess whose row cannot be completed, including an unknown clave 1626 and agrarian excess; a sale within three years of a later afectación (LIRPF art. 28.3), because its route changes.
- Registered, localized refusal: a date before service; a second disposal without correction; `scrapping` with proceeds; a donation; a new claim past the boundary; missing opening history for the calculation, though not for the baja; no table class for a required excess counterfactual; a foral resident, reusing the existing refusal.

**Outline, which may evolve within the commitments.** `src/cadrumo/domain/renta/actividad_asset/disposal.py` holds the record, reason enum and pure calculation, with no I/O and no form knowledge. `lifecycle.py` carries the optional record and validates the boundary; `claims.py` takes the shortening exception and the disposal-revision reference; `errors.py` gains the refusals. `src/cadrumo/application/actividad_asset/history.py` applies baja and supersession in one compare-and-swap mutation. `activity_asset_contracts.py`, `activity_asset_executors.py` and `registered_operations.py` add `ledger.actividad-asset.dispose` and a read-only `ledger.actividad-asset.disposal-calculate`. `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py` owns form projection, coordinated with Step S08.

## Rationale

The append-only record wins because the lifecycle contract already requires immutable history and the law needs both the prior years and the baja to compute cost. Computing R from the minimum, not from claims alone, is the only reading consistent with RIRPF art. 40. A blocking note for an unroutable result is preferred to silent omission, because omitting a gain understates income, while a refusal would deny the operator the calculated figure.

## Consequences

- An element leaves the register with its revisions and claims intact, and libro registro baja fields gain a source.
- A taxpayer with no claims still gets a lawful net value, and a smaller deduction never blocks a return.
- A late baja changes an already-calculated year, so the calculation revision must consume the disposal revision ID or the drift gate of Step S09 will not see it.
- Until clave 1626's meanings are found, rows that need it carry a blocking note. This is the known limit of the decision.
- The manual example at part 1 line 36479 charges 486 for half of 2025, above the 482.01 day-count maximum, so the product gives 169,726.01 against the manual's 169,730. It serves only as an arithmetic oracle and that difference is expected.
- Reconsider if a source fixes the counterfactual coefficient, the disposal-day convention, scrapping or clave 1626, or if the DYCTEA original of TEAC 01524/2017 differs from the reproduction.

## Amendment 2026-10-30, later

Authorized by the operator's ruling of 2026-10-30 that amortization is not a blocker. The accepted body is preserved; where it differs, this section governs.

- A baja never blocks a return. A gain, loss or excess whose row cannot be completed, including agrarian excess, a sale within three years of a later afectación and unknown opening history, is a non-blocking finding that keeps the calculation unresolved where no figure is known. The sentences calling these blocking notes, and the consequence on clave 1626, no longer apply.
- Missing opening history still refuses the calculation of the disposal figure itself, not the baja and not either return.
- Boxes are bound per revision through the `activity_asset_disposal` family: excess 0179 or 1478; gain and loss 1654 and 1639, 1843 and 1832, 0304 and 0305. Agrarian excess has no established line and stays a finding.
- Clave 1626: AEAT's Renta help gives clave 5 as other elements afectos to an activity, read from irpf-2022 to irpf-2025. This triggers the Reconsider clause on 1626; where the clave depends on a fact not recorded, it stays a finding.
