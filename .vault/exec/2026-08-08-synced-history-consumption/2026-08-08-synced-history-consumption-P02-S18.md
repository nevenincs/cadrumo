---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:2a5fc43c73a592e523e013333a930e34ce952aa6fb49cedeeae099e311eacec8'
step_id: 'S18'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Declare a treatment for the seventeen carries that have none, because an undeclared treatment cannot later be cited as authority for having consumed the value. Fifteen previous_filing bindings and both iva_compensation_annual_partition bindings are governed by no dependency classification at all, spanning Modelo 100 negative-base carry, Modelo 130 prior pagos and negative results, Modelo 131 negative results across four revisions, Modelo 353 prior Modelo 322 figures, Modelo 720 prior-year valuation baselines and Modelo 390's two compensacion partition slots. Each declaration is grounded in that row's own provisions and never by analogy to a sibling modelo, since AEAT surfaces do not transfer between modelos and a Modelo 720 valuation baseline and a Modelo 130 negative result are not the same kind of carry. Gate: every one of the seventeen carries a declared treatment with its own legal refs and source refs resolving in the legal catalogue, no two are justified by the same transferred rationale, and the registry loads clean.

## Scope

- Registry dependency classifications and construct membership for the twelve S18 carries.
- Generic direct-previous-filing closure validation and real mutation coverage.
- The affected command-sequence contracts and their CLI-generated goldens.

## Description

- Declare the twelve S18 source-modelo classifications from their own existing legal and source references.
- Associate every classification with the construct that owns its direct carry.
- Make the registry validator fail closed when a direct previous-filing source has no dependency-bearing classification, is relabelled `non_dependency`, lacks target coverage, or omits a required legal reference.
- Remove duplicate sequence setup where the canonical seed already supplies the invoice evidence.
- Regenerate changed goldens only through the sequence generator.

## Outcome

The prior undeclared population is closed: twelve carries are owned by S18 across Modelo 100, Modelo 130, Modelo 131, and Modelo 720; Modelo 353's three carry declarations are separately owned by S35. The two Modelo 390 annual-partition bindings were already classified.

The validator consumes the prior-filing resolver's canonical source-modelo key. Its loaded mutation coverage proves missing factual-evidence classification, missing relation-less direct-annual-settlement classification, and `non_dependency` relabelling are refused without a modelo-specific exception.

## Verification

- `aeat --format json app registry verify` passed with `verified=true`.
- The current loaded-authority probe found 21 direct `previous_filing` bindings and zero missing or `non_dependency` source-modelo classifications.
- Focused registry validation and classification suite: 85 passed in 27.56 seconds.
- Focused calculation, resolver-join, and Modelo 720 work-unit suite: 31 passed in 27.96 seconds.
- Ruff passed for the validator and S18-owned registry, calculation, and resolver tests.
- All fourteen S18 isolated sequence checks and all five owning-page coherence checks passed under the public 180-second timeout. The P03.S41 record contains the exact sequence and timing inventory.
- The feature-scoped Vault check completed successfully; plan validation completed with the pre-existing `PLAN022` ordering warning.

## Notes

The `verification-reports-modelo-303` contract had duplicated the canonical seed's evidence capture and attachment. P03.S41 removed the duplicate body frames and refreshed that exact generated golden through the canonical CLI; its isolated and page-coherence gates both passed. No generated JSON was hand-authored.
