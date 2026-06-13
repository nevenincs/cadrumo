---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S02'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-130-pagos-fraccionados-carry with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# extend _PreviousModeloSelector model validation so the new span mode is mutually exclusive with period, source_periods, and source_period_offset_from_target and stays a direct previous_filing binding under _is_direct_previous_filing_binding, then verify the relation-source collision gate validate_slot_source_hygiene accepts the new mode without a carve-out

## Scope

- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`

## Description

- Added a model validator branch that rejects `prior_quarter_expanding_span = true` when combined with `period`, `source_periods`, or `source_period_offset_from_target`, raising an explicit mutual-exclusivity error naming the conflicting field set.
- Confirmed `_is_direct_previous_filing_binding` classifies the span mode as a direct `previous_filing` binding (same canonical mechanism as the casilla-15 saldo-negativo carry), so the relation-source collision gate `validate_slot_source_hygiene` accepts it without any carve-out entry.

## Outcome

The expanding-span mode is a well-formed direct `previous_filing` binding that is mutually exclusive with the legacy single-offset / explicit-period selector fields and clears the relation-source collision gate with no carve-out. Landed in commit `6c25cd69a`.

## Notes

Keeping the carry a direct `previous_filing` binding is the load-bearing choice from the ADR's Option B: it reuses the enrolled direct-previous-filing resolver and avoids the dormant-relation collision the aggregation-taxonomy ADR closes.
