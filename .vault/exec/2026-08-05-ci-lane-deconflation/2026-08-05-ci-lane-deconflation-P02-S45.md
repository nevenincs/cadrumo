---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:59865091e6c507ae3f4641e5ae29fa50c762e34cf98891fce61a5d251b071cb7'
step_id: 'S45'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# THE PROPERTY IS SELF-SEALING, AND THAT IS THE CAMPAIGN'S STRUCTURAL RESULT RATHER THAN A MISCONFIGURATION REPORT. A module that no automatic lane collects can carry a COMMITTED collection error indefinitely, and two do at HEAD. The gate that enumerates them is itself integration-marked, so the default lane never collects it, and the only workflow that would run that gate has never once passed in its entire history. The break, the gate that would catch the break, and the lane that would run the gate are all on the same unreachable side of one predicate, so nothing in the apparatus can surface the gap from inside it. That is categorically different from saying a gate is misconfigured, and it is the answer to the question this campaign opened with. Everything below is the predicate that produces it. THE PREDICATE, RESTATED AT THE ALTITUDE THE EVIDENCE SUPPORTS. This was recorded as a docs-lane defect and it is a general property of path-filtered triggers that survives fixing the docs workflow entirely. Three instances are measured in three different workflows, found by two agents working from opposite directions. The docs lane fires on docs, dev/docs and the terminology data while no docs trigger in any workflow names src/cadrumo Python sources. The agent-harness lane reaches the JSON-envelope and rule-surface gates while its trigger paths exclude the CLI tree those gates validate. And six recipes are invoked by no automatically triggered workflow at all, three of which are additionally non-blocking in the only lane that runs them. The durable statement is that a gate runs on a push only if a lane's marker expression SELECTS it and an automatic event FIRES that lane, and that failing either reports identically as absence from a FAILED list. A THIRD AXIS HIDES INSIDE THE SECOND and must be stated with it, because a recipe can pass the trigger test and still reach nothing. The dev-conformance recipe fires automatically and its marker expression does admit integration, so an axis-A reading scores it as an automatically-firing integration lane, while its invocation names only dev trees and it therefore reaches no src/cadrumo gate at all. The marker was never the binding constraint there. The invocation's own path arguments were, so any claim that a gate is reachable must name the trigger paths, the marker expression AND the invocation paths, and this repository has an instrument for the marker axis and none for the other two

## Scope

- `the plan and .github/workflows and justfile as the mapping's subject`

## Description

- Derive the recipe-to-workflow mapping mechanically from the justfile and the
  workflow set, rather than restating the row's counts.
- Partition every test and check recipe by whether any workflow invokes it, and
  whether any AUTOMATICALLY TRIGGERED workflow does.
- Cross the dispatch-only set against the continue-on-error steps in ci-full.
- State the predicate at the altitude the evidence supports.

## Outcome

THE PREDICATE. A gate runs on a push only if THREE independent conditions all
hold: an automatic event fires a lane, that lane's marker expression selects
the test, and that lane's invocation paths reach the file. Failing any one of
the three reports identically -- as absence from a FAILED list. This
repository has an instrument for the marker axis and none for the other two.

The third axis is the one that hides, and it hides inside the second. The
dev-conformance recipe fires automatically and its marker expression does admit
integration, so a reading that checks trigger and marker scores it as an
automatically-firing integration lane. Its invocation names only dev trees, so
it reaches no `src/cadrumo` gate at all. The marker was never the binding
constraint there; the invocation's own path arguments were. Any claim that a
gate is reachable must therefore name all three, and a claim that names two is
not a weaker version of the right claim but a different and false one.

THE MEASUREMENT, derived mechanically rather than counted by hand. Of 22
workflows, 11 are automatically triggered and 11 are dispatch-only. Of the
test and check recipes:

- 26 are invoked by NO workflow whatsoever.
- 6 are invoked ONLY by a dispatch-only workflow, all of them by ci-full:
  `check-format`, `check-pre-commit`, `test-channel-artifacts`,
  `test-dev-tooling`, `test-integration-parallel`, `test-integration-serial`.
- Exactly 3 of those 6 are ADDITIONALLY non-blocking in that one lane, via
  `continue-on-error`: `test-integration-parallel`, `test-integration-serial`
  and `test-dev-tooling`.

The row asserted six and three from a hand count. Both reproduce exactly under
mechanical derivation, which is worth stating because the numbers now rest on a
repeatable method rather than on one reading. What the derivation adds is the
26, which the row folded into its six and which is the larger surface: a recipe
no workflow invokes is a declaration, and a declaration is not a run.

THE SELF-SEALING RESULT, which is the campaign's structural answer rather than
a configuration report. A module no automatic lane collects can carry a
COMMITTED collection error indefinitely. The gate that would enumerate such
modules is itself integration-marked, so the default lane never collects it.
The only workflow that would run that gate is ci-full, which has never once
passed in its entire history. The break, the gate that would catch the break,
and the lane that would run the gate all sit on the same unreachable side of
one predicate. Nothing inside the apparatus can surface the gap from inside it.

That is categorically different from "a gate is misconfigured", and it is the
answer to the question this campaign opened with. A misconfiguration is found
by reading the configuration. This is found only from outside, by asking of
each gate on which event, under which marker, and against which paths it
actually executes -- which is why it took two agents working from opposite
directions to find three instances in three different workflows.

## Notes

This row is a statement rather than a change, and it closes as one. Its value
is that the predicate is now written down at an altitude that survives fixing
any individual workflow: repairing the docs lane entirely would leave every
sentence above true.

The scope is deliberately NOT widened into building the missing instruments.
Two of the three axes have none, and an instrument for either is a real piece
of work with its own design question -- a trigger-path checker and an
invocation-path checker are different tools, and the second must reason about
justfile recipe arguments rather than YAML. Rowing them here would have
produced a shell. Naming the gap precisely is what this row can honestly
deliver, and it is what makes the next author's scoping cheap.

One correction to the row's own framing, recorded because the row invites it:
the durable statement is not that path-filtered triggers are the problem. Two
of the three measured instances are not trigger defects at all -- the
dev-conformance instance is an invocation-path defect and the dispatch-only six
are an event defect. Attributing the class to path filters would have narrowed
it back to the docs-lane reading the row explicitly says it outgrew.
