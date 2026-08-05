---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:d74209f3f2dfb9d9f3cab062047d8028e0e2d244a00841e6f4c667faaa6c4ee6'
step_id: 'S22'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Author the ADR reshaping the overview.calendar payload, the resource_link remedy the gate names cannot apply to a computed verb with no persisted record and the irreducible floor leaves only 622 characters of headroom

## Scope

- `src/cadrumo/entrypoints/mcp`

## Description

- Establish what caused the breach before choosing a remedy.
- Measure every candidate remedy directly rather than reasoning from commit sizes.
- Record the ruling, the two measurement traps the investigation hit, and the limits of the evidence.

## Outcome

The decision record is `2026-08-05-ci-lane-deconflation-overview-calendar-payload-adr`. Its
ruling reshapes the profiles array to a per-profile summary, on structural grounds rather
than arithmetic; suppresses pydantic auto-titles fleet-wide as a separable decision pending
an independent verdict; and refuses both raising the budget and stripping descriptions.

The row's own text frames the problem as an irreducible floor leaving 622 characters. That
framing is accurate and turned out not to be the decisive fact. The decisive fact is that the
20589 decomposes as definitions of 15844 plus roughly 4734 of envelope spine common to every
verb and untouchable by any payload change, so the verb-specific allowance is about 13300
against 15844 of payload definitions. The payload is over its real allowance before the
envelope is counted, which is why the reshape is adopted on structural grounds instead of
because it clears a threshold — it barely clears it.

## Notes

**The cause is a conjunction, and that is the finding most likely to outlive the record.**
Two commits 24 minutes apart jointly cost 3661 characters; removing either alone leaves the
verb over budget. A bisect hunting the one bad commit would have exonerated every commit it
tested. Threshold regressions are where bisection is most natural to reach for and where it
cannot see the cause by construction.

**Two readings were wrong before the measurement settled it, and both were plausible.** One
held the payload had always been over and a newly-enrolled gate merely surfaced it; the other
identified a single commit as the cause. The record keeps three compatible facts separate
rather than collapsing them — a correctly calibrated ratchet, a genuine breach, and three days
of blindness because the lane carrying the gate had never run — because collapsing them is
what produced both wrong readings.

**A growth-rate claim was drafted and withdrawn.** The verb shows three apparent growth steps,
but two were the verb being built out rather than accreting onto a settled surface, so the
regime that matters has one observation. One observation is not a rate. The argument that 629
characters of headroom is thin now rests on subtraction alone: the one measured breach cost six
times that margin. The peer who supplied the trajectory data identified the overreach in its own
work and supplied the replacement formulation.

**Verification of every figure was first-hand.** Each measurement in the record was taken at
HEAD rather than accepted from a report, including the peer figures that agreed — the
envelope decomposition, the model-versus-descriptor discrepancy, and the titles saving all
reproduced exactly. One reported figure disagreed with mine and the reporter was right: a
counterfactual that removes a property without pruning the definitions it orphans understates
the recovery, giving 19766 where the correct figure is 17378. Both traps are recorded in the
ADR rather than left in this record, because they will cost the next reader time regardless of
which document they arrive at.

**One input remains unconfirmed and the record says so at the point of the decision.** The
title suppression's saving is measured, its self-attack was performed by the same person who
proposed it, and an independent verdict is outstanding. The record marks the decision pending
rather than asserting it, and names the two specific gaps: whether an SDK or client path reads
output-schema titles invisibly to a repository search, and whether the suppression mechanism
reaches every nested model in one change.
