---
tags:
  - '#adr'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e09f760d4643638845b45508672fb425a3442acb94da70cad42591ced8b69e41'
related:
  - "[[2026-07-21-ci-discipline-adr]]"
  - "[[2026-07-20-ci-speed-redesign-adr]]"
  - "[[2026-06-01-registry-period-code-union-cli-boundary-adr]]"
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - '[[2026-08-05-ci-lane-deconflation-step-check-attribution-audit]]'
---
# `ci-lane-deconflation` adr: `one consolidated plan, and verdict granularity follows determinism` | (**status:** `accepted`)

## Problem Statement

The CI-lane work left residual open rows governed by three separate accepted records —
`2026-07-21-ci-discipline-adr`, `2026-07-20-ci-speed-redesign-adr`, and
`2026-06-01-registry-period-code-union-cli-boundary-adr`. Two questions had to be answered
before that residue could be tracked at all, and neither is answered by any of the three.

Where do the rows live? Each row could have gone to the plan of whichever ADR governs its
surface, leaving three partial plans and no document from which the campaign's remaining
work is legible.

And how many verdicts does the integration suite deserve? It runs as two passes — a
parallel pass under xdist and a serial pass at `-n0` for tests that mutate or read
process-global state. Whether those are one enrolled step or two is a decision with
consequences for what can ever go blocking.

## Considerations

This record is deliberately short, and two-thirds of what a reader might expect to find
here is deliberately absent.

The enrolment posture for a lane that is red on its first real run — non-blocking on
arrival, with a written commitment to flip — is **already decided** in
`2026-07-21-ci-discipline-adr` D6.6, which records the posture, the reasoning (blocking on
an untriaged backlog either stops releases or trains the fleet to read a permanently red
release-verdict lane as normal), the `continue-on-error` mechanism, the code-comment
contract, and an explicit commitment that it MUST flip once triage completes. This record
does not restate any of it and makes no ruling on it. The only sliver not in D6.6 — that
the flip is the operator's to make rather than the agent closing the backlog — is a
closure criterion, and it lives in the plan's Verification section where closure criteria
belong, not in a second decision record.

Likewise absent by intent: the two new T1 tiers, the byte-identical carve-out and its
gate, frozen installs, the "declared is not run" distinction, and the backlog
measurements. All are D6's, and an ADR that re-narrates its neighbours is how a corpus
acquires two homes for one fact.

## Considered options

**For the tracking question.** Distribute the rows across the three governing ADRs' own
plans — rejected: it fragments one campaign's residue across three documents, and no
reader asking "what is left" gets an answer from any of them. Or consolidate into one
feature-scoped plan carrying all three ADRs in `related:` — adopted.

**For the verdict question.** Enrol the integration suite as one step covering both passes
— rejected, see D2. Or enrol it as two independently-verdictable steps — adopted.

## Constraints

The consolidated plan owns no decisions of its governing ADRs; it tracks execution against
them. Its rows inherit their authority from the `related:` chain rather than from this
record.

This record must not become the campaign's second narrative. Where a fact has a home in
D6, in the workflow, or in the plan's own Verification section, this record cites it.

## Implementation

### D1 — The campaign's residual work consolidates into one feature-scoped plan

`2026-08-05-ci-lane-deconflation-plan` is the single tracking document for the residue of
this campaign, at L2, with all three governing ADRs in `related:`. Rows inherit their
authority from that chain; the plan makes no decisions of its own.

This follows an established shape in this vault rather than inventing one:
`2026-07-30-open-work-consolidation-adr` governs a pure tracking-and-consolidation plan on
the same basis. The framework's own roll-up guidance is the general form — multi-component
work, each component carrying its own decision record, rolls up into a single plan as the
tracking document with every governing ADR listed in `related:`.

The practical consequence is that the campaign's remaining work is legible from one
document. The cost is that a reader who arrives at any one of the three governing ADRs
will not find the residue there, which is what this record exists to make discoverable.

### D2 — The integration lane's two passes stay independently verdictable

The parallel pass and the serial pass remain two enrolled steps, each carrying its own
verdict, and MUST NOT be merged into one step.

The reason is not topical — both run the integration suite — but a property of the two
passes that differs: **the parallel pass is deterministic and the serial pass is not.**
Every parallel-pass failure that triage could not attribute to a peer mid-edit was a real,
reproducible defect. The serial pass carries wall-clock budgets measured on a box CI shares
with the dev machine and the agent fleet, so two of its three failures move with load
rather than with code.

Behind a single step, the deterministic half could never go blocking without the
load-sensitive half coming with it — which would wire the release verdict to a load
average. The rejected alternative is therefore not merely less convenient; it is
unshippable in the direction the campaign is trying to travel, because it makes the good
half hostage to the flaky one permanently.

The generalisable ruling: **verdict granularity follows determinism, not topic.** Two
passes of one suite deserve two verdicts when one can be trusted to block and the other
cannot. A future enrolment that bundles a load-sensitive assertion with a deterministic one
under a single step is making the same mistake this decision rejects.

The serial pass's budgets need converting from wall-clock to process CPU-time before that
step can be trusted to block at all; the repository's control-plane invariant already
settles that class (CPU-time asserted, wall advisory only). Until then the two steps'
verdicts are not merely separate but on different timelines, which is itself the argument
against joining them. Measurements and the current step configuration live in
`.github/workflows/ci-full.yml`; they are not restated here.

## Rationale

Both decisions answer questions the three governing ADRs do not reach, which is the test
this record was held to before it was written. D1 answers where the residue lives; D2
answers how many verdicts one suite earns. A third candidate — the enrolment posture and
its flip contract — was dropped from this record on inspection, because
`2026-07-21-ci-discipline-adr` D6.6 already holds it in full, including the flip
commitment. Recording it again would have created exactly the duplicate-authority drift
this campaign spent its effort removing from the period-code boundary.

D2's reasoning currently exists only as a comment on the workflow step it describes. That
is a fragile home for it: the comment vanishes with the steps if someone merges them, which
is precisely the change the decision exists to prevent. A decision whose only record is
attached to the thing it forbids changing cannot survive that change.

## Consequences

- The campaign's residual work is tracked in one plan; a reader of any single governing ADR
  must follow the `related:` chain to find it.
- The two integration steps are structurally separate and may reach blocking status at
  different times. Merging them is a decision reversal requiring an amendment here, not a
  workflow tidy-up.
- Exec records for the plan's rows can now be scaffolded through the owning verb, which
  refuses to create them for a feature with no ADR. That refusal is what surfaced this
  record's absence; it is a side effect of D1, not its purpose.
- This record makes no ruling on the enrolment posture, the tier table, the carve-out gate,
  or the backlog measurements. Those remain D6's, and a future reader looking for them
  should go there.
