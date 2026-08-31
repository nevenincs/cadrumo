---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:f49b0b3c19c395adccfab251e22a642527bd3c3cae3021ba166ce45dc4a3a498'
step_id: 'S73'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Rule on the Modelo 390 simplificado applicability question raised by the sibling Step, and record the grounding that settles it. THE RULING: regimen simplificado applicability is CONDITIONAL, so the M390 annual-summary handoff requirement must consult it rather than firing on the revision's declaration alone. This is grounded, not argued. LIVA art. 122 Uno, read in the bundled consolidated corpus at ley-37-1992-art-122, states the regime 'se aplicara a los sujetos pasivos ... que reunan los siguientes requisitos' and then lists three: personas fisicas or entidades en regimen de atribucion de rentas whose members are all personas fisicas, activities determined by regulation, and a prior-year volume-of-operations limit. A taxpayer in regimen general meets none of the regime's conditions and its M303 boxes 51-58 -- the exact source_casilla_ids these bindings read -- carry nothing. THE CODEBASE ALREADY AGREES WITH THIS READING, WHICH IS THE DECISIVE POINT: a closed vocabulary exists for precisely this judgement. M303RegimenSimplificadoScope carries REGIMEN_SIMPLIFICADO_NOT_CLAIMED and REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED, and m303_regimen_simplificado_scope_for_composition maps M303RegimeComposition.GENERAL -> NOT_CLAIMED and SIMPLIFIED or MIXED -> EVIDENCE_REQUIRED, refusing an unknown composition rather than defaulting. Four production sites already gate on it with the same spelling, applicable = not scope_decision.is_not_claimed: _m303_regimen_simplificado.py, filing/_projection.py, modelo/_m303_filing_evidence.py, and the scope module itself. The M390 annual-summary requirement is the SOLE site that never consults it. So this is not a new rule to invent but an established one with a single unenrolled call site, which is why it is an amendment to the accepted 2026-07-01-modelo-303-regimen-simplificado-adr rather than a competing decision. IMPLEMENTATION SHAPE, and it deliberately spans two sites because one alone would be wrong: the resolver in _m303_regimen_simplificado_annual_summary.py must, after projecting the requirement and BEFORE calling _source_work_unit, derive the scope from the target work unit's own profile and return an empty resolution when NOT_CLAIMED -- the modelo-gated deriver returns None for a 390 work unit, so the profile-based m303_regimen_simplificado_scope_for_profile(active_taxpayer_profile(target)) is the correct entry. The guard _require_m303_regimen_simplificado_annual_summary_handoff must then widen its antecedent from 'the revision declares the family' to 'the revision declares it AND the family is applicable', because a resolver that legitimately produces no handoff for a general-regime filer would otherwise trip the biconditional it currently enforces. THAT IS NOT THE LOOSENING WARNED AGAINST: the guard keeps refusing an unexpected or missing handoff on every path where the family applies, and only stops demanding one where law says the regime does not reach the taxpayer. NOT YET IMPLEMENTED -- deliberately. The blast radius is every 390 filer, the change touches production tax logic at two sites, and this project requires the decision be recorded before the code moves. Verify against test_verify_modelo_revision_refuses_m390_when_prior_filings_are_not_clean, whose taxpayer declares IVARegime.GENERAL and which must then reach its INTENDED unclean-priors refusal instead of the aggregation-binding one. WATCH FOR A SECOND, SEPARABLE QUESTION while implementing: that test seeds NO 303 work units at all, so it also probes whether a 390 may be computed with no quarterly filings present. Requiring a filed 4T is defensible on its own for an annual resumen, but it must not be enforced by the SIMPLIFICADO resolver acting as messenger for a general-regime taxpayer -- keep the two apart

## Scope

- `src/cadrumo/application/calculations/_m303_regimen_simplificado_annual_summary.py`
- `src/cadrumo/application/modelo/_calculation_actions.py`
- `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S73.md`

## Notes

- Decision provenance only: accepted `2026-07-01-modelo-303-regimen-simplificado-adr.md` was amended by `a232800b14d15bc65427d81dc12c261ad57cbef4`. The amendment rules that the annual-summary handoff is conditional on regimen-simplificado applicability, with GENERAL not claimed and SIMPLIFIED/MIXED evidence-required.
- S73 made no source change and has no historical or fresh pytest receipt. S74 owns Route B threading; S75 owns production implementation in `94187f454c55ddd1df6265d7f66601c0df4fdfe2`. Its historical test claims are not S73 evidence.
- Resolver and `_calculation_actions.py` carry shared staged and unstaged work while pytest suites are active, so no fresh test was run.
