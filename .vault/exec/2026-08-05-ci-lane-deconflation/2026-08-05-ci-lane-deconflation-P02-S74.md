---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:275a99ec36fe450452878c4d7aae97c88fce36c600ad653e43ba7a42dd8d2250'
step_id: 'S74'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Correct the implementation shape recorded for the M390 simplificado applicability ruling, which cannot be built as first written. The sibling Step's ruling stands unchanged and is fully grounded; only its HOW is wrong, and finding that out before writing code is the point of recording it. The recorded shape had the annual-summary resolver derive the scope itself via m303_regimen_simplificado_scope_for_profile(active_taxpayer_profile(target)). That import is NOT AVAILABLE to it: both functions are defined only in src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py, an underscore-private module, and the resolver lives in application/calculations -- a different package. aeat-architecture-boundaries forbids a cross-package private import outright, and forbids fixing it by mechanically stripping the underscore: a contract needed outside its package must HARD-MOVE to a public defining module with every consumer updated and the old path deleted atomically, in one commit. TWO ADMISSIBLE ROUTES, and the second is preferred. ROUTE A, relocation: hard-move the scope derivation to a public defining module under application/modelo, sweeping all seven current consumers (_calculate_input.py, _export.py, _m303_filing_evidence.py and four test modules) in a single explicit-path commit tagged relocation:m303_regimen_simplificado_scope, with pytest --collect-only clean immediately before. That is a whole Step of its own and drags an unrelated relocation into a tax-correctness fix. ROUTE B, threading, PREFERRED because it already IS the established pattern rather than a new one: application/calculations/_m303_regimen_simplificado.py does not derive the scope either -- it RECEIVES M303RegimenSimplificadoScopeDecision as a parameter at two call sites, and that type is publicly reachable from domain.iva, which the calculations layer already imports. So the annual-summary resolver should likewise be GIVEN its applicability rather than reaching for it, supplied by the caller that already holds the profile, keeping the derivation single-homed in application/modelo and adding no new cross-package edge. Decide the exact carrier when implementing: the resolver's constructor is the narrower change, a CalculationSourceContext field the broader one, and the guard in _calculation_actions.py needs the same signal to widen its antecedent, so prefer whichever hands both sites one value from one derivation. SEPARATE PRE-EXISTING DEFECT FOUND WHILE MEASURING, not caused by this work and not to be silently absorbed into it: application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py and application/filing/tests/test_m303_export_applicability_internal.py BOTH already reach across packages into that private module. Route A would sweep them by construction; Route B leaves them standing and they want their own fix

## Scope

- `src/cadrumo/application/calculations/_m303_regimen_simplificado_annual_summary.py`
- `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py`
- `src/cadrumo/application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py`
- `src/cadrumo/application/filing/tests/test_m303_export_applicability_internal.py`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S74.md`

## Notes

- Design-correction provenance only: plan row source is `b6c0e78700d80b8706d626448c38e944b5ef05f3`; accepted ADR amendment provenance is `a232800b14d15bc65427d81dc12c261ad57cbef4`. S74 keeps S73's conditional-applicability ruling and corrects only the infeasible cross-package private-import shape.
- The downstream implementation belongs to S75: `94187f454c55ddd1df6265d7f66601c0df4fdfe2` implements Route B by supplying applicability to the calculations resolver while retaining the derivation in `application/modelo`. This record cites that relation only; S74 made no source change.
- S74 has no historical or fresh pytest receipt. The plan's S75 route-suite claim is not S74 evidence. Active shared WIP and live pytest processes precluded a fresh run.
- The two pre-existing private test reaches remain out of scope: `application/aggregation/tests/test_invoice_accumulative_cross_modelo_periods.py` and `application/filing/tests/test_m303_export_applicability_internal.py`.
