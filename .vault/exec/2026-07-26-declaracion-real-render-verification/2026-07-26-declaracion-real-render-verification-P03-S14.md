---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:6ed0a8e6c4b311aa6763d3e83fe65743fb8c5e1100b8d37d4fe890a03834307d'
step_id: 'S14'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Add the Modelo 100 boundary gate asserting the exclusion and its stated reason, green and not mistakable for a pass

## Scope

- `src/cadrumo/adapters/inbound/declaracion/tests`

## Description

Modelo 100 is excluded from the real-render gate because its extracted values are
not the amounts on the page. That was recorded in the module docstring, which a
later author is free to not read, and an exclusion nobody is forced to confront
is how the original defect survived.

The exclusion is now asserted. For each of the three real specimens, the gate
requires that the extracted values continue to DISAGREE with the constant the
specimen's own sanitiser manifest declares.

The assertion is deliberately inverted, and its failure message says so: it
passes while the profile is broken and fails once it is repaired, and the correct
response to a failure is to enrol Modelo 100 in the specimen table and delete the
test, not to adjust it. An author who enrols Modelo 100 without repairing the
merge has to delete an assertion whose message explains why they should not.

## Outcome

Three parametrised cases, green, and the module is at 45 passing.

The gate also guards its own premise: it refuses if extraction returns nothing at
all, so it cannot pass vacuously against a profile that has stopped extracting
rather than one that extracts wrongly.

Its sensitivity was measured rather than assumed, and it is narrower than the
shape suggests. Driving a repaired extraction over `2021-0A` makes exactly one of
19 recovered targets agree with the declared constant, casilla `0510`. The other
18 print `1.001.000,00`, a form the manifest never declares, because the
sanitiser is length-preserving and recorded only the eight-character variant. So
one target carries this gate, and a repair that somehow left `0510` merged would
slip past it. That limitation is written into the test rather than left for a
reader to discover.

The module docstring's account of where the merge happens was wrong and is
corrected in the same change. These targets are `named_label` and read page text,
not the word path, so separating the fonts is necessary and not sufficient: the
box number is printed after the value and `named_label` captures the last token,
so the separated form yields the box number instead. That is the fact that makes
the repair an estate-wide change rather than a local one.

The gate was proven to bite by feeding it the output of the prototype repair
rather than by assuming: with the current parser zero targets agree and the gate
passes; with a repaired extraction one target agrees and the gate fails, naming
the target and instructing the reader to enrol and delete. Failure is the good
outcome here, which is why it was worth demonstrating rather than reasoning
about.

## Notes

The narrow sensitivity is a symptom of a corpus defect rather than of the gate's
design, and it is tracked separately: the Modelo 100 sidecars declare one
sanitiser constant while the sanitiser wrote two. Correcting the manifests would
widen this gate from one carrying target to nineteen at no cost, and would also
restore the real-render gate's manifest check as a usable substitution detector
for that modelo. Until then this gate is thin but not vacuous.

A companion change landed alongside and is worth noting here because it protects
this module's premise: the gate now selects profiles by calling the production
selector rather than re-implementing its filter, so it can no longer certify a
profile the parser would not choose.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on.
