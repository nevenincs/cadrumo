---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:624709659a550b6c79d53cc1c97c5848c773dab6345d1b364408249abce73db3'
step_id: 'S419'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# repair Modelo 100 non-business profile calculation bindings and prove the Catalunya pensioner-landlord tariff through the real CLI

## Scope

- `src/aeat/application/modelo/ src/aeat/application/aggregation/ src/aeat/_data/registry/aeat/modelos/100/ src/aeat/**/tests/`

## Description

- Add a calculation-only profile predicate for declared economic activity in Modelo 100 revision 2025.
- Short-circuit the estimación-directa formula to zero for a non-business taxpayer while retaining the manual modality branch for economic activity.
- Cover the predicate through profile-source provenance, direct Renta scenarios, and real encrypted-store CLI calculation journeys.
- Repair the review-discovered direct-estimation scenario inputs and prove the economic branch still refuses an absent modality.

## Outcome

The fully declared Catalunya pensioner/landlord now calculates Modelo 100 without an activity or estimación-directa override. The real CLI result carries positive cuota íntegra estatal casilla 0545 and cuota íntegra autonómica casilla 0546. Formula 0075 first checks the profile-derived activity predicate; false short-circuits to zero, while true retains its existing normal-versus-simplified manual modality selection.

The direct-estimation registry scenarios explicitly declare the predicate as true and preserve their active-branch provenance. The real economic-activity CLI persona continues to refuse calculation when the modality is absent. Ruff, 58 source-mesh/Renta tests, 7 registry-scenario tests, and 6 real CLI profile-preflight tests passed. Independent review found and then approved the repaired direct-scenario coverage.

## Notes

The profile predicate uses the canonical comma-delimited income-category fact and normal profile-source provenance. Identity/export bindings remain outside the calculation mesh; their discovery presentation does not control the tariff calculation.
