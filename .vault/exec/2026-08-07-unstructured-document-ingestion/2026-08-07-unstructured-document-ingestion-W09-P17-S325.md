---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:1e4f4dfdb1dc568c4144bdfa5e2940203abee2f24295beb955bb6af6466da246'
step_id: 'S325'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Record the postal-attribution disposition in the ADR, the half of the role-evidence row a shipped gate cannot deliver. The decision is settled and enforced - address values are attributed deterministically in code by co-location from the document layout, and a property gate refuses any attributed address field acquiring a role-evidence key, checking the rendered prompt as well as the contract table. What is missing is a DECISION RECORD: the reasoning lives in a test docstring and an exec record, so the next author meets the refusal without meeting the argument, which is how a gate gets read as an obstacle rather than as a conclusion. Carry the context-budget reasoning that decided it, that the design target is a lowest-bound vision model and every added key costs the fields already in the prompt, and state it as a precondition on any consumer of postal-derived territory

## Scope

- `.vault/adr`

## Description

- Read the governing ADR for an existing postal-attribution disposition before
  writing one.

## Outcome

PREMISE FALSE, and the row should not have been opened. I opened it earlier
today on an incomplete read, and the disposition it asks for is already in the
governing ADR as its sixth amendment -- stated more completely than the row
asked for.

That amendment renames the axis to PARTY ATTRIBUTION and corrects the record's
own earlier enrolment-by-example, so the requirement attaches to any field the
classification consumes per-party rather than to tax ids. It rules that
attribution for non-identity fields is DETERMINISTIC CO-LOCATION rather than
more prompt, in those words, and gives the reason the row wanted carried: the
design-target model's context budget is a hard constraint and evidence keys
without a consumer are review theatre. It names the gate -- the transposition
fixture, where swapped address blocks must yield correct attribution or a
refusal and never silently swapped territories. It states the honest interim
as a visible precondition, with the attribution-unverified stamp and the
review-gate advisory. And it makes the once-per-counterparty confirmation the
working mitigation.

No change made. The row is closed as an error of mine rather than a delivery.

## Notes

THIS IS THE SAME ERROR AS THE ROW THAT SPAWNED IT, one layer along, and worth
recording as such. On the role-evidence row I implemented a widening before
reading the gate that forbids it. Here I opened a documentation row before
reading the ADR that already contains it. Both times the surface I needed was
one search away and I wrote first.

The correction matters beyond the checkbox: the sixth amendment says the
role-evidence keys do NOT widen from two to six, and the change I attempted
would have widened them from two to four. So the widening was not merely
gate-refused, it was ADR-refused, and the earlier record's claim that the
disposition "has no decision record" is itself wrong. That record is corrected
in the same commit rather than left standing.
