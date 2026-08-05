---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:610659b013dd254e47c566e8b7665f48f6a655dbe631c7863c5080108cf33a17'
step_id: 'S32'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Acquire the complete authoritative 2025 0613 cap and rounding oracle matrix and return it to SOL before any producer promotion

## Scope

- `src/cadrumo/_data/corpus/manual_oracles`
- `src/cadrumo/domain/contribuyente/tests`
- `.vault/research`

## Description

- Ran VaultSpec-RAG before the official-source search, recalling the accepted parity ADR, the S17 research boundary, current 2025 profile/casilla surfaces, and the real-behavior test lane.
- Checked the official 2025 AEAT pages for the monthly amount, annual cap, two-month worked example, six-month worked example, and casilla `0613` filing location.
- Compared the published observations with the required seven-, eight-, and twelve-month rounding boundary and the required per-child effective-spend matrix.

## Outcome

The complete authoritative matrix was not acquired. Official 2025 material confirms up to `83.33` euros per qualifying month, a `1,000` euro annual per-child limit, `166.67` for two months, and `500` for six months, but it does not publish independent 2025 expected `0613` outputs for the seven-, eight-, and twelve-month rounding boundary or the required spend, subsidy, employer-payment, both-parent, turning-three, and unequal-two-child cases. The cross-year `666.64` and `583.33` observations therefore remain an authority discrepancy, not a safe 2025 producer rule.

S32 remains open and no value was enrolled as a `0613` oracle. No registry, formula, binding, relation, profile, application, or test producer was changed.

## Verification

- Official-source URLs and the exact acquired observations are recorded in `2026-08-05-modelo-parity-rollup-s17-0613-cap-rounding-research`.
- The research records that the next admissible gate is an independent executable oracle or an explicit SOL ruling resolving the rounding and per-child matrix.
- No production or schema files were modified; no tests were added because an evidence-only test cannot manufacture the missing oracle.

## Notes

- RAG grounding was available for the parity ADR, S17 evidence, current profile/casilla code, and existing real-behavior tests.
- A LUNA MAX delegation was attempted but stopped before discovery because the delegation precondition required unavailable SOL validation evidence; it made no changes.
- The concurrent registry/application-wide IRP invocation-shape remediation remains outside this tranche.

## Live oracle addendum (2026-08-05)

The evidence-only acquisition was extended through the official AEAT Renta WEB Open simulator after VaultSpec-RAG request 16afa387a55842ea8bb39547a7d35b67 returned the active S30, S17, S28, and S32 grounding. The simulator URL was:

https://www2.agenciatributaria.gob.es/wlpl/PARE-RW25/OPEN/index.zul?EJER=2025&TACCESO=COLAB

The official help entry for the unauthenticated simulator is:

https://sede.agenciatributaria.gob.es/Sede/eu_es/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-web-open.html

All inputs were synthetic audit data and no declaration was presented. The official clock showed 05/08/2026 19:04:13-19:04:39 for the two-child run and 05/08/2026 19:12:31-19:13:26 for the post-birthday run.

### Acquired independent observations

The live guarderia surface returned the following values using effective non-subsidized spend:

- blank expense and zero selected months: blank, semantic zero;
- 100.00 spend and two months: 100.00;
- 2,000.00 spend and two months: 166.67;
- 2,000.00 spend and six months: 500.00;
- 2,000.00 spend and seven months: 583.33;
- 2,000.00 spend and eight months: 666.67;
- 2,000.00 spend and twelve months: 1,000.00.

A two-child run used 2,000.00 effective spend for each child, with two selected months for a child born 01/01/2023 and six selected months for a child born 31/12/2022. The second child reported 11 maternity months because it turned three during 2025. The live per-child guarderia values were 166.67 and 500.00, with final 0613 of 666.67, proving unequal per-child caps are summed rather than collapsed into one total-spend minimum.

A post-third-birthday run used a child born 01/01/2022, with only February selected and 2,000.00 effective non-subsidized spend. The live child result was 83.33. With the first child still at 166.67 for two months, final 0613 was 250.00. This is a live 2025 observation for a complete month after the child turned three.

The 2/6/7/8/12-month values resolve the prior 2025 rounding uncertainty in favor of retaining 1,000 / 12 at full precision through the multiplication and rounding the result to cents. Multiplying a displayed 83.33 monthly value would not produce the observed 666.67 for eight months.

### Updated boundary

The live oracle closes the cap, rounding, per-child aggregation, unequal-cap, and post-third-birthday portions of S32. It does not provide separate parent-paid, subsidy, exempt-employer, or multi-right-holder observations. The multiple-right-holder controls were disabled for the synthetic single declarant with ordinary child linkage. Those dimensions remain open and must not be inferred as zero.

S32 therefore remains open pending a SOL ruling on whether this live evidence is sufficient for the remaining effective-spend and multi-right-holder contract. No registry, formula, binding, relation, profile, application, or test producer was changed, and no value was enrolled as a production 0613 oracle. The concurrent registry/application-wide IRP invocation-shape remediation remains outside this tranche.
## Binding SOL closeout (2026-08-05)

The prior open-state outcome above is superseded by the binding ruling recorded after the live oracle replay.

RULING: APPROVE S32 closure strictly as authoritative oracle acquisition. No further rows are required to close S32 numeric oracle acquisition. This closes S32 only as the W06.P13 evidence gate. All 2025 `0613` producer promotion remains DEFERRED, and no external-grounding enrollment is authorized.

VaultSpec-RAG request IDs used for this closeout are `51ae4d3c659242ffb025ca2516611737` and `2e292d0a3ae2427d8a555aa75d6810b1`. The accepted vault search mode was available and its limitation is therefore recorded honestly. The service reported index integrity as unverifiable because no claim was returned; this search is discovery input, not proof.

The accepted live rows are blank/zero blank, `100 / 2 = 100.00`, `2,000 / 2 = 166.67`, `2,000 / 6 = 500.00`, `2,000 / 7 = 583.33`, `2,000 / 8 = 666.67`, and `2,000 / 12 = 1,000.00`. Unequal children yield `166.67 + 500.00 = 666.67`; a post-third-birthday child with one qualifying month yields `83.33`, and with the other child the total is `83.33 + 166.67 = 250.00`. These rows close the numeric cap, rounding, per-child aggregation, unequal-cap, and post-third-birthday portions of S32.

The runtime discrepancy remains explicit: the 2025 registry cap parameter is `None`; qualifying months are `1`; maternity months are `0`; the current helper result is `0`; and the live AEAT result is `83.33`. This exposes a dormant deficiency and does not authorize wiring, fallback behavior, or a compatibility path.

The minimum pre-promotion oracle remains open: (1) a non-degenerate effective-spend row with parent-paid amount, public subsidy, and exempt employer contribution, with net below cap; (2) an enabled multiple-right-holder allocation; (3) disjoint maternity and guarderia months; (4) partial overlap where count-minimisation differs from month-set intersection; and (5) after source-contract implementation, bundled Renta WEB Open replay plus independent real secure-profile-to-registry-engine reproduction.

Plan status after the companion record and plan update is `29/32`: S16 `OPEN/DEFERRED` with 0150 manual, S17 `OPEN/DEFERRED`, S18 `OPEN/DEFERRED`, and S32 `COMPLETE`. The eventual producer reverse invariant remains mandatory: computed casilla, identical formula ID on casilla and formula target, all bindings declared and resolved with provenance, and independent real-runtime replay. No production, registry, schema, formula, binding, relation, profile, persistence, application, test, corpus-enrollment, or IRP invocation-shape file was changed.
