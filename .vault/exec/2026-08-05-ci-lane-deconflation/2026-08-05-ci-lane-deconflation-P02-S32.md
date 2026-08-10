---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e65b1ac0b545336c57fe0f92cb2475ae7545bb1581cdf66b5252221c755f86fe'
step_id: 'S32'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Triage the reds that enrolment exposes

## Scope

- `dev/registry/tests`

## Description

- Run the enrolled selection and record what passes, what reds, and who owns each red.
- State whether the reds, if any, reflect on their authors.

## Outcome

What passes: all 138. What reds: nothing. Who owns each red: not applicable.

The triage this row was opened for does not exist. Every test in the enrolled selection passes, and the 24 deselected are the external-tool cases the sibling row's marker expression holds out by design. The row closes on a triage record with no entries, which is the honest close rather than a vacuous one, because the measurement was real and the record states its result.

The expected finding was rot. Thirteen modules that had never executed were assumed to have accumulated breakage in the dark, and the campaign-metadata docstring failures already measured elsewhere were read as the leading edge of it. That reading was wrong, and this record says so rather than quietly closing.

What the zero actually shows is sharper than the rot it replaced. One hundred and thirty-eight correct, passing tests were being produced into a void. The authors wrote them properly, marked them properly, and put them in a proper tests package beside an init file, and every assertion they wrote was discarded on arrival. This is not decay. It is verification value manufactured and thrown away, at roughly twelve modules a day.

That makes the enrolment's worth independent of what it found. It did not find bugs. It stopped the discarding, and a zero-red measurement today says nothing about tomorrow: the leak is that the NEXT module lands into the same void, and the only reason today's count is zero is that this campaign happens to write correct tests.

## Notes

The reds that do not appear here are not cleared by their absence. The campaign-metadata docstring failures are real and still open, and they are raised from outside this directory by the marker-integrity gate scanning dev docstrings. They were never reachable from inside it and are not this row's to close.

No author is criticised by this record, and the reasoning is worth keeping rather than assuming. Unreachability is invisible from inside the directory: nothing at an authoring site names the lane list that omits it, and reading a path list in a build file is precisely the knowledge the reachability gate exists to supply. A gate that is red supplies nothing to anyone, which is why the enrolment is the remedy and a reprimand would not have been.

The count is a working-tree number. One file in the executed set is uncommitted peer work, so a clean checkout runs slightly fewer tests. It passed, so it does not distort the verdict, but the figure is stated as what it is.
