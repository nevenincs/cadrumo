---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:f0cf4f19573a9c34b1b4fa8979d38c61c02aeb26af195bff7b529febb1ee36ee'
step_id: 'S12'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Advise when a declared descendant contributes to the minimo with no rentas figure on record, because the existing undeclared diagnostic returns early whenever descendiente facts exist and that early return reasons about a declared ZERO, which does not hold for a declared descendant whose rentas are simply absent and who therefore over-claims silently

## Scope

- `src/cadrumo/application/modelo/_minimo_descendientes_advisory.py`
- `src/cadrumo/application/modelo/tests/`

## Description

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
