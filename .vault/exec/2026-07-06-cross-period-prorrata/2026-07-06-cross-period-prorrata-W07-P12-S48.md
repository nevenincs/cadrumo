---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S48'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# re-ratify bienes inversion remaining source blocker

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/application/calculations/_bienes_inversion_regularizacion.py`
- `src/aeat/application/modelo/_bienes_inversion_advisory.py`
- `src/aeat/application/aggregation/tests/`

## Description

- Re-ran the S48 semantic grounding for `bienes_inversion_regularizacion` after prorrata enrollment moved it out of the deferred set.
- Confirmed the previous `promotion_depends_on=prorrata_regularizacion` trigger had fired and was now stale.
- Re-ratified `bienes_inversion_regularizacion` as still deferred, replacing the dependency trigger with a governed blocker: a live bienes-inversion resolver must declare/prove the Modelo 303 casilla 43 / Modelo 390 binding targets, map profile register rows to the definitive prorrata percentage, and handle art. 110 disposal cap facts.
- Removed the stale `promotion_depends_on` relation so the fired-trigger gate no longer reports a false dependency.
- Updated capital-goods calculation/advisory module wording so the remaining blocker is no longer described as merely waiting on prorrata-definitiva.
- Added an enrollment-status regression asserting the re-ratified bienes-inversion blocker has no prorrata dependency and names the remaining resolver/binding target.
- Ran the mandatory review pass; no critical or high implementation findings remain for S48.

## Outcome

- S48 is complete as a governed re-ratification, not a casilla-43 promotion.
- `bienes_inversion_regularizacion` remains in `DEFERRED_SOURCE_KIND_TARGETS`, but its deferral is no longer mechanically tied to the now-promoted prorrata source.
- The source-kind fired-trigger gate is clean and will flag any future stale dependency trigger.
- No capital-goods live resolver, source kind, registry binding target, or validator convention was introduced.

## Notes

- Verification passed: source-kind taxonomy, mesh parity, precedence ladder, enrollment-status, and prorrata source-mesh enrollment pytest slice (32 passed).
- Verification passed: bienes-inversion calculation/advisory pytest slice (15 passed).
- Verification passed: source-boundary, unresolved-diagnostics, source-mesh calculation, bucket aggregation flow, and local cross-period carry pytest slice (41 passed).
- The re-ratified blocker is intentional remaining work: design and prove a live capital-goods source resolver plus registry binding target before promoting casilla 43 / the M390 regularizacion field.
