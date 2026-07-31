---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-26'
body_hash: 'sha256:30fc59edafc92196bb1c3634952cada638d2ba803c6bf832857ff8ec0bdc3cf6'
step_id: 'S01'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
---

# Refuse a DESCARTADO unit in create_work_unit with an instructive message naming its state and a real next step, in the WorkUnitMutationRefusedError shape the same module already uses eleven lines below, rather than returning the discarded unit and letting every downstream verb deny it exists

## Scope

- `src/cadrumo/application/modelo/_work_lifecycle.py`

## Description

Close the stranded-filing-target defect at its source. A work-unit id is
content-addressed over bucket, modelo, filing year, period and registry revision,
so re-creating a discarded target re-derives the same id. Creation returned that
record with no state check, handing back a unit every downstream verb then
reported as absent.

This step was ordered ahead of the supersede transition deliberately: it is
reachable by an ordinary retry instinct rather than a specific sequence, it costs
the operator a filing target irrecoverably, and its remedy is enrolment under a
refusal shape the same module already carries.

## Outcome

Landed in commit `4eed7f80f0`.

`create_work_unit` now refuses a `DESCARTADO` unit instead of returning it. The
refusal carries the work-unit id, the state, the target coordinates, and who
discarded it and when, and it states the dead end rather than restating the
command that produced it — the previous downstream message told the operator to
"run work create first", which was the command that had just run.

Two things were found while implementing that were not in the step as written.

First, the fix is cheaper than the record implied: the same module already
refuses a discarded unit eleven lines below, so this is enrolment under an
existing refusal shape rather than a new mechanism.

Second, and consequentially, this change made an existing sibling message
provably false. The rename refusal advised "create a fresh work unit on the same
modelo / year / period to continue" — which this change turns into a hard
refusal. Its inline message and its locale string were corrected in the same
change rather than left standing, since prose asserting a guarantee that no
longer holds has a documented history in this repository of manufacturing false
audit findings on later passes. That key was verified to have exactly one
production consumer before being edited.

The four locale keys were authored through the locales CLI, never by hand-editing
a catalogue. They are not in this commit: a peer's broad commit `68d49cc36b`
swept all four into its own SHA while I was isolating my hunks from locale files
that also carried that peer's uncommitted censo work. The keys are in HEAD and
the tree is coherent, so nothing was lost, but they are attributed to a commit
that did not author them and correcting that would require rewriting history,
which is categorically forbidden here.

## Notes

The discovery mandate was satisfied against a recovered index, not assumed. The
code index had been truncated earlier in the session while reporting
`degraded_reasons: []`; before any coding it was re-measured at 68,502 chunks
against 3,671 tracked source files and validated with two semantically unrelated
probes that returned disjoint, correct canonical owners. A single probe returning
plausible results would not have been evidence.
