---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:186b6843a85f4c5f8a1255eb297e893f4e82bf11d8be92897fa009fd06faf395'
step_id: 'S12'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace minimo-descendientes-eligibility with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-08-04-minimo-descendientes-eligibility-plan placeholders are machine-filled by
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
     The Advise when a declared descendant contributes to the minimo with no rentas figure on record, because the existing undeclared diagnostic returns early whenever descendiente facts exist and that early return reasons about a declared ZERO, which does not hold for a declared descendant whose rentas are simply absent and who therefore over-claims silently and ## Scope

- `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`
- `src/cadrumo/application/modelo/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Advise when a declared descendant contributes to the minimo with no rentas figure on record, because the existing undeclared diagnostic returns early whenever descendiente facts exist and that early return reasons about a declared ZERO, which does not hold for a declared descendant whose rentas are simply absent and who therefore over-claims silently

## Scope

- `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`
- `src/cadrumo/application/modelo/tests/`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

The over-claim now has an operator signal. A declared descendant contributing to the minimo
with no rentas figure on record raises a non-blocking advisory naming the descendant and the
fix. The fail-open default is untouched, as required: this is a signal, not a semantics change.

The silent half carries more tests than the firing half, deliberately, because a blanket
advisory is worse than none. Silent when the figure is present, when it is present and ZERO,
when nothing is claimed, for a non-cohabiting or over-25 descendant, for a profile with no
descendientes, and for another modelo. The present-and-zero case is the important one: zero is
what an operator enters for the ordinary child, so treating it as missing would fire on nearly
every household with children.

One test exists because the silent direction could have passed for the wrong reason. If
persistence dropped a stored zero the way it drops empty optionals, the present-and-zero case
would pass because the DESCENDANT vanished rather than because zero was recorded. A round-trip
test pins that a stored zero survives as a zero while an absent one survives as absent. That
distinction is the entire advisory, and without the round-trip the suite would have been green
on a vacuous assertion.

The non-overlap with the sibling collector is pinned as a RELATION rather than as two
independent facts: one test asserts the sibling stays silent on this state while this collector
fires, so a later edit cannot quietly make both silent.

A structural choice worth recording. Determining whether a descendant would contribute needs
the non-income half of Art. 58.1 without the registry ceilings, which the collector cannot
resolve, and fabricating a thresholds object would have meant inventing registry values.
Rather than re-deriving cohabitation and age beside the existing predicate, that half was
factored out and the predicate now calls it. A descendant with no figure can never be excluded
by either income condition, so for that descendant eligibility reduces exactly to the extracted
predicate. One authority rather than two that can drift.

A defect the executor's own test caught, and it is the kind that would have shipped. The
diagnostic message is length-bounded by contract, and naming every descendant was the only
unbounded part. A twelve-child household overflowed it and turned the advisory into a hard
validation error -- at exactly the moment it had something to say, for the filer with the most
children at stake. It now names three and counts the rest, with a regression pinning it. Eleven
other cases passed; only the large-household case found it.

Gates: thirteen cases in the new module, and 1684 across the contribuyente and modelo suites.

OUTSTANDING, and it is the one thing this Step did not close. A late addendum asked for a test
proving the coordinator WIRING, not merely the collector in isolation, and it crossed with the
work. Coordinator verification: the collector IS wired and does fire in production. But no test
drives that coordinator and observes it, so deleting the wiring line would fail nothing -- the
same gap the addendum was raised about, now inherited by the new advisory. Dispatched
separately.

Also not verified: no end-to-end run reads the advisory off a real envelope; the length bound
is enforced by the model rather than the formatter, so a future prose edit could re-cross it
outside the shape the regression exercises; the advisory fires per calculation rather than per
filing; and a partnered filer with an undeclared figure now receives two advisories on the same
casilla, both true and both actionable, without anyone assessing whether two at once reads as
noise.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
