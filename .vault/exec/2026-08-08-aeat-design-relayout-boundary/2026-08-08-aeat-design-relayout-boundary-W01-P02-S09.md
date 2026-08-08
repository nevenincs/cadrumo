---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:aef763ef2767da4c5620812c9eb21fde16690628e6ea01bf576311b328536e3f'
step_id: 'S09'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Add the description-keyed companion check for unnumbered slot meaning flips

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`

## Description

- Re-measure the pass with the canonical box marker in place, applying the pre-flight check that the probe must not declare its own copy of the thing under test.
- Ship the discrimination rule that separates a changed slot meaning from a relabelled containing block, refusing where it cannot.
- Mark in the verdict any boundary resting solely on this pass.
- Prove it by suppressing the pass alone from outside the repository.

## Outcome

**The verdict now names 22 of 22 boundaries.** Modelo 390 moved from 8 re-layouts to 9, which was the last outstanding gap against the independently derived union. Per revision: Modelo 200 one, Modelo 303 eight and four, Modelo 390 nine.

**The canonical box marker was the precondition, and the numbers show it.** Measured before that fix, this pass asserted **1462** changes on Modelo 200's single boundary. Measured after, it asserts **1**. The flood was not imprecision in the rule; it was 5538 five-digit numbered fields being classified as unnumbered by a four-digit marker and pouring into a population defined as "slots carrying no box number". Across every gated span the pass now reports 33 assertable flips, 10 slots it refuses to judge, and 1 pair it abstains on. Refusing to ship over the mis-derived population was correct: shipping it would have added 1461 pieces of mislabelled evidence that then read as signal.

**The discrimination rule, validated rather than asserted.** AEAT writes these descriptions hierarchically, joining the containing block to the field's own name. The rule compares the FINAL segment: a changed leaf is the slot's own meaning, an unchanged leaf under a changed prefix is the block being relabelled and is not reported. Against the three hand-judged reference cases it classifies all three correctly, including the one that matters - Modelo 111's `Identificacion. Ejercicio` becoming `Devengo. Ejercicio` is declined, because only the heading above the field moved while the field still carries the ejercicio. Modelo 390's `Lorca` becoming `Reducciones (nota 2)` at a fixed 17-byte slot is reported, and the leaf comparison isolates exactly those two words out of a much longer description.

**Where it cannot separate, it refuses.** A description with no separable leaf on both sides is counted and printed for review rather than asserted, and the count rides along with the boundary's evidence. Ten such slots exist across the gated spans.

**The precision problem is handled by marking, not by pretending it is solved.** This pass runs roughly one false positive in three on individual verdicts, and a measured example survives in the shipped corpus: Modelo 303's 2014/2015 pair reports a leaf going from `regimen simplificado` to `Regimen Simplificado (RS)`, which is a rewording with a parenthetical added. It costs nothing there, and the reason is the distinction the design turns on - **a false positive on a boundary other signals already name adds noise to the evidence, not a wrong split.** Three signals already name 2014/2015. The only case a reader must judge rather than act on is a boundary this pass names ALONE, and that case is invisible unless the verdict says so, so the failure text now marks it `DESCRIPTION-KEYED PASS ONLY`.

Exactly one boundary in the whole gated corpus carries that mark: Modelo 390 2018/2019, the Lorca slot. It was hand-verified before shipping, it is corroborated by the occupancy signal reporting the same sheet-5 offsets 223 and 543 retiring at a later boundary, and it sits outside the prescripcion window so no authoring decision rests on it.

**The flattened-PDF abstention is retained and is load-bearing.** The PDF backend collapses a document to one synthetic sheet, so the key stops identifying a slot and starts colliding across pages. A corpus-wide run without the abstention returned **15366** "changes" that were overwhelmingly unrelated fields compared against each other.

**Applied the standing pre-flight check for the first time deliberately rather than after the fact.** Before measuring, the probe was inspected for its own copy of the box marker; it had one, and the first patched attempt silently failed to apply, which the unchanged 1462 immediately exposed. Had the check not been in place the pass would have been evaluated against a blind population for the second time in two Steps.

## Verification

    uv run --no-sync pytest <this module> -p no:randomly -n0 -q
    1 failed, 12 passed in 366.68s

    modelo 200 '2024-y-siguientes'   1 re-layout
    modelo 303 '2009-y-siguientes'   8 re-layouts
    modelo 303 '2023-y-siguientes'   4 re-layouts
    modelo 390 '2010-y-siguientes'   9 re-layouts   (was 8)
    ... 2018/2019 DESCRIPTION-KEYED PASS ONLY (1 unnumbered slot re-described ...)

Mutation proof, from **outside** the repository, suppressing this pass alone while every other signal keeps running:

    PYTHONPATH=<scratch>/mut uv run --no-sync pytest <this module> -p no_description_pass -p no:randomly -n0 -q -rA
    MUTATION APPLIED: description-keyed pass suppressed, holder confirmed, 14 firing pair(s) removed
    FAILED ...::test_a_boundary_only_the_description_pass_sees_is_reported_and_marked_for_review
    modelo 390 revision '2010-y-siguientes' spans 8 re-layout

Modelo 390 falls back from 9 to 8, losing exactly the boundary this pass alone sees, which is the demonstration that the signal is what finds it. The plugin refuses rather than passing when the pass reports nothing before suppression, when the rebinding does not take, and when the verdict builder resolves a different function.

**A peer landed a sibling gate mid-Step that pins which revisions still span, and this change moves a count it might have pinned.** Rather than assume, it was run: `3 passed`. It pins the SET of spanning revisions, not their boundary counts, and this change adds boundaries inside existing spans without adding a spanning revision, so nothing broke.

    uv run --no-sync ruff format --check <this module>   All checks passed
    uv run --no-sync ruff check <this module>            All checks passed!
    uv run --no-sync ty check <this module>              All checks passed!

## Notes

**Attribution: fourth sweep.** A peer bare whole-index commit took the pass itself into HEAD alongside 32 files of other agents' work under a subject describing unrelated changes. The working tree was byte-identical to HEAD afterwards, so the state tested is the state that shipped. The review assertion committed normally.

**The M303 printed-versus-design distinction was applied as a named case, not a caution.** The Modelo 303 diseño declares boxes 70, 71, 74, 75, 76 and 77 and not 72 or 73, and the export layout matches, so an absence there is AEAT's and not the registry's. This pass reads only slots present in BOTH designs at the same position and width, so it cannot report a printed-only field as a registry omission by construction; the hazard was checked rather than assumed away.

**Not measured.** Whether the ten refused slots contain a real meaning change is unknown by design - that is what refusing means, and they are printed for a human rather than counted as boundaries. The one flattened-PDF pair remains unmeasured by this signal rather than clean.
