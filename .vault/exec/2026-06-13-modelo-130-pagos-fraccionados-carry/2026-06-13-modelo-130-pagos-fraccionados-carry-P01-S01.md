---
tags:
  - '#exec'
  - '#modelo-130-pagos-fraccionados-carry'
date: '2026-06-13'
step_id: 'S01'
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

# check git status for peer WIP, then add a target-relative prior-quarter expanding-span selector mode to _PreviousModeloSelector that resolves to all same-ejercicio quarters strictly preceding the target (2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}), bounded by max_year_delta 0, emitting a tuple of (year_delta, period) anchors into the existing required_period_anchors_for_target path

## Scope

- `src/aeat/domain/calculations/registry/_bindings_previous_filing.py`

## Description

- Checked git status for peer WIP on the selector module before editing.
- Added the `prior_quarter_expanding_span: bool = False` facet to `_PreviousModeloSelector` and the `_prior_quarter_expanding_span_anchors(target_period)` helper resolving each target quarter to its strictly-preceding same-ejercicio quarter set (1T to empty / absent-by-design, 2T to {1T}, 3T to {1T,2T}, 4T to {1T,2T,3T}), all at `year_delta = 0` to honour `max_year_delta = 0`.
- Wired the emitted `(year_delta, period)` anchor tuple into the existing required-period-anchor path so the span feeds the established multi-anchor aggregation sum resolve without a new resolve channel.

## Outcome

`_PreviousModeloSelector` now expresses a target-relative expanding-span carry over same-ejercicio prior quarters, emitting the full preceding-quarter anchor set into the existing multi-anchor sum path. The empty 1T span is recognised as absent-by-design. Landed in commit `6c25cd69a`.

## Notes

This is the dormant grammar half; the casilla-05 binding flip that consumes it lands in P02 coupled with the P03 cross-period handling. The aggregation that summs the emitted anchors per the AEAT instrucciones (`sum(max(0, prior 07)) - sum(prior 16)`) is the `prior_pagos_fraccionados` op added in the same commit.
