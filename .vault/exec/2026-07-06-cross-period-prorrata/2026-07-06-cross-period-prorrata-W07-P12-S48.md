---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S48'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S48 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The re-ratify bienes inversion remaining source blocker and ## Scope

- `src/aeat/application/aggregation/_source_mesh.py`
- `src/aeat/application/calculations/_bienes_inversion_regularizacion.py`
- `src/aeat/application/modelo/_bienes_inversion_advisory.py`
- `src/aeat/application/aggregation/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
