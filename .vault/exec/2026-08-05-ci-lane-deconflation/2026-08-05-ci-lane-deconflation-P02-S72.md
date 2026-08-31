---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1ba204456b5ce97baa5488dddc523f78609b6c6328d2db8057a8321dbdb06381'
step_id: 'S72'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Settle whether a Modelo 390 calculation may hard-require a filed Modelo 303 4T source unconditionally. OPEN, ADR-GRADE, DELIBERATELY NOT RESOLVED IN CODE -- this is a tax-semantics question and the rules forbid settling it by assumption. Carrier for the single remaining red test, test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean, whose diagnosis is recorded in the sibling Step. The mechanism: m303_regimen_simplificado_annual_summary_requirement returns non-None whenever the revision declares the binding family, and the resolver's _source_work_unit then RAISES unless exactly one filed same-bucket 303 4T work unit exists, with _require_m303_regimen_simplificado_annual_summary_handoff enforcing the matching biconditional at calculate. Applicability is keyed on the REVISION alone and never on the taxpayer. Boxes 74-83 are regimen simplificado boxes that EVERY 390 form carries, so all four epochs declare the family and the requirement fires for every 390 filer -- including the GENERAL-regime taxpayer this test declares, who has no simplificado activity at all. Both readings are defensible, which is exactly why it needs a ruling rather than a patch: an annual IVA resumen does presuppose the year's quarterly autoliquidaciones, so requiring a 4T source is coherent; equally, routing a general-regime filer through a REGIMEN SIMPLIFICADO handoff to obtain it is not, and 2026-07-01-modelo-303-regimen-simplificado-adr already establishes a narrower applicability vocabulary -- not-claimed is neutral and must reject Orden and module rows -- that this requirement never consults. Modelo 390 is the IVA resumen anual and general regime is the majority population, so if the second reading is right the blast radius is most 390 filers. WHAT NOT TO DO: do not relax or delete the guard. It landed 2026-08-14 in e2797f1aad to keep the handoff on its one mesh-owned arrival path, and the declaration is not the new thing -- the deleted 2010-y-siguientes revision declared the same family, so the bindings predate the guard. If the ruling is that applicability must be taxpayer-aware, the change belongs in the REQUIREMENT projection consulting the established not-claimed-is-neutral vocabulary, not in loosening the biconditional that protects the arrival path

## Scope

- `src/cadrumo/application/modelo/_calculation_actions.py`
- `src/cadrumo/application/calculations/_m303_regimen_simplificado_annual_summary.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S72.md`

## Notes

- S72 deliberately deferred the ADR-grade tax-semantics decision. It made no source or ADR change and claims neither a historical nor a fresh pytest receipt.
- Downstream lifecycle, not S72 implementation: S73 ruled that the annual-summary handoff is conditional on regimen-simplificado applicability; S74 selected Route B threading to preserve package boundaries; S75 implemented that resolution in `94187f454c55ddd1df6265d7f66601c0df4fdfe2`.
- Live source has staged and unstaged peer work in the resolver and `_calculation_actions.py`, while shared pytest suites are active. A fresh route receipt was therefore not run and must not be inferred from S75's historical claim.
