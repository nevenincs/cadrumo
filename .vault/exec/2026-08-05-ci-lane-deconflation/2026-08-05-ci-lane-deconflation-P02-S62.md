---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d54ea21d1cb15ec90bf63fdd2f155c94b998bd7992dd52258ac9cb4593386d00'
step_id: 'S62'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Close Modelo 720's live blank-emission path by giving a diseno-declared constant its own binding source kind. DONE 2026-08-28 under the accepted ADR `2026-08-28-registry-narrow-mechanism-widening` (decision C), executed as P01 of `2026-08-28-registry-narrow-mechanism-widening-plan`. THE DEFECT: M720's `tipo-de-registro` @1 and `modelo-declaracion` @2-4 were `source = "manual_input"` on both records, so the application prompted the taxpayer for AEAT's own record-type marker and modelo number; the prompt is answerable-blank and a blank emitted at those positions behind a valid digest, producing a file AEAT cannot parse. The diseno (aeat-dr-720) states all four as constants in its own field text. AN EARLIER LITERAL FIX WAS REVERTED because three tests pin 'M720 must represent every casilla through a binding, never an inline export field'; the tests were right and the edit was wrong. WHAT LANDED: `BindingSourceKind.DESIGN_CONSTANT` (33 members) with `design_constant_bindings.py` carrying a selector and an accumulating build-time validator, wired into both dispatch tables; the selector adds a check the manual channel could never make -- the value must FILL its declared run exactly, proved biting on '72' and '7200' against a 3-byte run, because padding a mis-read diseno silently is how it reaches the wire. Enrolled on the calculate route via a NEW SIBLING pseudo-owner `CalculationRouteDesignConstantOwnership` rather than relaxing the manual owner's Literal pins -- the ADR's own principle applied to the fix's own code, so every existing pin stays intact. M720's four bindings re-sourced, keeping `data_type = "integer"` deliberately because switching to 'text' could change padding and justification of emitted bytes. THEN THE JOIN, which the first pass did not close: `_record_literals` read only inline LITERAL fields, so a record declaring its constant through a binding looked like a record with no constants. Extended it to read BOTH declared channels and threaded the map through `_belongs_to_layout`, `_join_record`, `_missing_report` and `_layout_failure`. This is NOT the widen-a-matcher move the ADR forbids: both channels are declarations validated at registry build, and the checker simply could not see the second. The ratchet was aligned to call the same `_design_constant_values`, because a gate seeing fewer channels than the checker reports debt that does not exist -- the third time today a gate overstated. VERIFIED: registry Verificado=True, 43/43 M720 tests green, both sheets JOIN their record, coverage 0 complaints through the real per-record join, ratchet gate green with the two M720 entries deleted (23 -> 21)

## Scope

- `src/cadrumo/core/aggregation.py`
- `src/cadrumo/domain/calculations/registry`
- `src/cadrumo/application/modelo/calculation_route.py and the M720 bindings`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/bindings/0001-bindings.toml`
- `M` `src/cadrumo/application/modelo/calculation_route.py`
- `M` `src/cadrumo/core/aggregation.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `A` `src/cadrumo/domain/calculations/registry/design_constant_bindings.py`
- `M` `src/cadrumo/domain/calculations/registry/m303_differentiated_deduction_projection.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S62.md`
- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py src/cadrumo/domain/calculations/registry/tests/test_modelo_720_registry.py src/cadrumo/domain/calculations/registry/tests/test_modelo_720_binding_derived_record_extent.py src/cadrumo/domain/calculations/registry/tests/test_modelo_720_binding_derived_records_are_complete.py src/cadrumo/application/modelo/tests/test_calculation_route.py` -> `pass` (77 passed in 209.32s)
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/aggregation.py src/cadrumo/application/modelo/calculation_route.py src/cadrumo/domain/calculations/registry/bindings.py src/cadrumo/domain/calculations/registry/design_constant_bindings.py src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py src/cadrumo/domain/calculations/registry/m303_differentiated_deduction_projection.py src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py src/cadrumo/application/modelo/tests/test_calculation_route.py` -> `pass`

## Notes

- Historical reconstruction: immutable commit `ce7ed9c74ef76a656170e5c8060e4b68fa510779` is the content-based landing evidence. It changes the nine implementation paths above and its message names the design-constant binding source and narrow mechanism gate. No literal historical command output or pre-existing ci-lane P02.S62 execution record is available, so the contemporary verification above is distinct evidence rather than a reconstruction of historical output.

