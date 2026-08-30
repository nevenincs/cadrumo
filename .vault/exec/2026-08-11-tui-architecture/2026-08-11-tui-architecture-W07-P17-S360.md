---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:a213544842eef3b7c9aa84978f891a1c6338377d61a621b137a6a5a5d142c765'
step_id: 'S360'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Restore the summary's wrapping margin at narrow widths -- THE CONTENT-SIDE HALF OF A DEFECT WHOSE LAYOUT-SIDE HALF IS ALREADY FIXED, so this row is not redundant with that fix and must not be closed by pointing at it. RULED OPTION A: the objective is the MARGIN, not the row count. CLOSING CONDITION, STATED STRUCTURALLY RATHER THAN AS A CONSTANT: THE PROGRESS LINE IS NO LONGER THE BINDING CONSTRAINT -- THE WORK-UNIT ID LINE GOVERNS THE UPPER TRANSITION. That survives content-width, chrome and indent changes because it names a RELATIONSHIP between two measured quantities rather than either one's value. WHY THE FORM CHANGED: an absolute target was invalidated twice in one afternoon by this campaign's own other rows. The `Collapsible` disclosure moved the content-width model from about `screen - 7` to about `screen - 14`, and the 7 columns removed by deleting the duplicated registry revision cancelled against it exactly -- a real improvement that produced ZERO movement in the number the row was to be judged by. An absolute measured constant is a valid target only while everything holding it still is stable, and in an active campaign the thing holding it still is precisely what the campaign is changing. OBSERVATION, dated 2026-08-30 and taken under the geometry of that date -- evidence, not criterion, so its going stale is informative rather than disqualifying: sweep gives 9 summary rows at 80 columns, 8 from about 90 to 97, and 7 from 98 upward, so the transition sits at 97/98 and the canonical 120-column sample clears it by 22 columns, against 6 before this work. Also remove the line 5 / line 1 duplication regardless -- the trailing `2024` is the registry revision already shown two rows above, it saves 7 of the 20 columns needed, and it is redundant either way. WHAT THE NARROWING EXCLUDES, stated because a campaign may not narrow its own completion criterion silently: AT THE 80x24 FLOOR THE OPERATOR SEES 5 OF 8 SUMMARY ROWS, AND THE REMAINING 3 ARE REACHABLE ONLY THROUGH A SECOND SCROLL AFFORDANCE NESTED INSIDE THE BODY'S OWN. Measured `region.height=9`, `container_size.height=5`, `virtual_size.height=8`; the outer 9 includes 2 rows of border and 2 of padding, so the content box is 5. An operator scrolling inside a scrolling panel cannot tell which one will move, and nothing announces that three rows exist below the fold. That is a real residual cost, it is what the original 6-row condition was reaching for, and Option A does not pay it. The 6-row condition was never reachable: it was written before anyone knew a 64-character content-addressed id sat on line 0. THE TWO WRAPPING LINES, with real rendered widths at 200 columns: line 0 `Unidad de trabajo` plus a 64-character id = 88 columns; line 5 `Progreso` plus `in_progress · 0/600 · calculation_completeness_manifest · aeat-dr-100-2024-dictionary · 2024` = 108 columns. The other four are 24 to 32 columns and never wrap. Content width is screen width minus 7, a model that PREDICTS BOTH MEASURED TRANSITIONS EXACTLY -- line 5 needs a screen of 115, matching the swept 114/115, and line 0 needs 95, pinning the lower step at 94/95 rather than the swept 90-95 band. Full profile: 10 rows at 60-70, 8 at 80-90, 7 at 95-114, 6 at 115 and above. Line 0 is IRREDUCIBLE without truncating an addressable identifier an operator may need to copy; whether a full 64-character id belongs on that surface at all is NOT settled here and is opened as its own row. RULE WORTH CARRYING, and what produced these numbers: MEASURE AN ESTIMATE AT THE MOMENT SOMETHING STARTS DEPENDING ON IT -- cheap because most estimates never carry weight, reliable because the trigger is a change in the estimate's ROLE rather than a remembered discipline, and its corollary is that a number nothing depends on can stay wrong indefinitely. HOW TO MEASURE: drive the session fixture's own generator rather than rebuilding its composition -- `compose_runtime_ports.__wrapped__()` from `src/cadrumo/conftest.py`, `next(gen)` to enter, `next(gen, None)` in a finally to unwind; without it a standalone driver over `build_real_modelo_work_review` raises `RuntimeError: profile custody infrastructure has not been composed`. Read rendered lines from the Static's `_content`, not `renderable`, which does not exist on it. AND SWEEP RATHER THAN BISECT: a bisection on the predicate 'is anything wrapping' returns only the LAST boundary and gives no sign that earlier steps exist, which is how the second transition stayed hidden through an interpolation and a bisection before a sweep found it

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/work_review.py summary line construction`
- `and the width at which it wraps`

## Changes

- `M` `src/cadrumo/entrypoints/tui/modelo/view/work_review.py`
- `M` `src/cadrumo/locales/en/flows.yml`
- `M` `src/cadrumo/locales/es/flows.yml`
- `M` `src/cadrumo/locales/ca/flows.yml`
- `M` `src/cadrumo/locales/hu/flows.yml`
- `verify:` sweep under the new geometry -> `9 rows at 80, 8 from ~90 to 97, 7 from 98 up; transition 97/98`
- `verify:` expanded summary at three sizes -> `one scroll owner, hidden=0, geometry CLEAN`
- `verify:` `pytest review + visual suites -n0` -> `164 passed, 2 pre-existing unrelated failures`

## Notes

Option C, ruled after Option A-prime was measured and rejected. The progress
line kept its NAMED denominator, which this module's own invariant requires;
the registry revision came off it because it is already its own summary line
and repeating it added no fact; and `denominator.source_ref` moved to a
labelled line of its own rather than being dropped.

WHY NOT DROPPING `source_ref`, which was measured and would also have met the
target: it is grounding. `aeat-calculation-grounding` requires `source_refs`
to travel from the registry source to the operator-facing surface, and
`aeat-dr-100-2024-dictionary` is what answers "who says there are 600
casillas". Satisfying this module's invariant, which names `kind` and not
`source_ref`, is not the same as satisfying the grounding rule, and the
grounding rule is the one with teeth. A-prime reached the transition at 97/98
by removing 30 columns of provenance; C reaches the same transition and keeps
it.

THE CLOSING CONDITION CHANGED FORM, and that is the durable part. It was
"transition measured at 94/95, 120 clearing by 25". That constant was
invalidated by this campaign's own work: the `Collapsible` disclosure moved
the content-width model from about `screen - 7` to about `screen - 14`, and
the 7 columns saved by removing the duplicated revision cancelled against it
exactly -- a real improvement producing zero movement in the number the row
was judged by. Restated as a relationship: THE PROGRESS LINE IS NO LONGER THE
BINDING CONSTRAINT; THE WORK-UNIT ID LINE GOVERNS. An absolute measured
constant is a valid target only while everything holding it still is stable,
and in an active campaign that is precisely what is being changed.

THE RESIDUAL, in measured terms and not narrowed: the summary still does not
fit whole at the 80x24 floor. Expanded there it is 11 rows. What changed is
that this is now a cost to the operator who EXPANDS it rather than to the one
who opens the screen -- the disclosure means the expanded height no longer
evicts the casillas table -- and nothing is clipped: `container_size` equals
`virtual_size` at every declared size, so `hidden=0`.

Verified before committing to C, because the alternative was reintroducing
the defect three rows had just removed: the expanded summary produces NO
second scroll owner at any declared size, and `geometry_band` reports CLEAN
under the WIDENED predicate rather than the old one.

`S362` remains open on its own merits and is NOT settled by this row. The
work-unit id now SOLELY governs the transition, so whatever `S362` decides
about displaying a full 64-character id moves that boundary directly, and
with it what `S107` should sample.
