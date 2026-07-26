---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S09'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
---

# RESOLVED, the binary identity question was ruled NO on the ground that prevention beats recovery on a filing-grade path, needing no persisted-schema or identity change and therefore no operator sign-off

## Scope

- `see 2026-07-26-evidence-revision-identity-adr`

## Description

This record is written after the fact to close a
`plan-closure-requires-exec-records` gap. The step closed without a source change
and this record states why, rather than manufacturing activity that did not
happen.

## Outcome

**Closed without source change. The step was a decision gate, and the decision
was taken and recorded.**

The step existed because every mechanism on the table at that point changed the
id a recalculation derives for revisions that already exist. That is a
behavioural change on filing-grade records a human files outside the application,
and the parent decision's Constraints reserve exactly that class for operator
sign-off rather than an implementer's judgement. The step's purpose was to hold
implementation until the binary question — does the evidence gap enter revision
identity — had an answer from someone entitled to give it.

The question was ruled NO, and the sign-off the step was waiting on turned out
not to be required, because the answer removed the change that would have needed
it. The mechanism adopted alters one severity assignment. It touches no persisted
schema, adds no field, moves no revision id and mutates no finalized record, so
it never enters the reserved class. That is not a way around the constraint; it
is the constraint being satisfied by not making the change it governs.

The decision was routed to an independent reasoner rather than taken by the
implementer holding the step. That routing is the substantive content of this
step and is the reason it can be closed rather than deferred: the ruling located
the defect at the severity assignment rather than at identity, which is a
different diagnosis than either the parent decision or the investigation that
blocked on it had reached.

Two prior steps depended on this answer and resolve from it. S08's identity
carrier is unnecessary once the gap is prevented rather than recorded, and S03's
withdrawn supersede transition needed the same discriminator. Both are recorded
separately.

## Notes

An implementer reading this record should not take from it that identity changes
can be closed by finding an alternative. The reserved class was avoided here
because a better mechanism existed, and the escalation happened first — the step
was held, not routed around. Had the promotion not been available, the sign-off
would still have been owed.

The evidence-digest option remains available and remains the more faithful model
of the domain. Nothing ruled here forecloses it; if it is ever wanted it is a
separate decision with an operator in it.

The plan row for this step is checked and was not touched by this record.

Semantic search was unusable throughout the campaign: the code index reports
roughly 68 sections against about 4,546 files while self-reporting healthy, and
searches timed out at 120 and 300 seconds against a service whose latest indexing
job had failed. No claim here rests on a search miss.
