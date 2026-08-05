---
tags:
  - '#adr'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:f1ffca62425d471e94b053465ba6807c5b7b5bf356d6afe0ce9ccdc86f6ccc6c'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
---
# `ci-lane-deconflation` adr: `the breach is a conjunction and the payload is over its real allowance` | (**status:** `accepted`)

## Problem Statement

The `overview.calendar` MCP verb's output schema serialises to 20589 characters against an
18000-character per-verb budget. It is the only verb of 297 over; second place is 16610 and
third 15831, so the fleet is not crowding the ceiling.

The gate's named remedy — move the bulk array to a `resource_link` — does not apply to this
verb. Resolution re-runs a read verb as a supervised subprocess over persisted state; this
verb is computed from the clock with no persisted record, so a link would return rows
recomputed at resolution time rather than the rows the tool call summarised. That is a
correctness regression, not an inconvenience.

Two questions therefore had to be answered before any reshape could be chosen: what actually
caused the breach, and what the payload's real allowance is.

## Considerations

**The budget is a ratchet, not an external limit.** The gate's own comment records it as
"set with headroom above the current maximum so it locks the posture without churn, yet
catches a doubling". It was calibrated to a measured maximum on 2026-07-08, not derived from
a protocol constraint or a client's context window. That matters twice over: it makes
"the number is arbitrary" a weak objection, and it makes the ratchet's own calibration a
usable datapoint about what the verb measured when it was set.

**The gate is integration-marked.** Integration-marked modules under the source tree had
never run in CI until that lane was recently enrolled, so the ratchet was correctly set and
unwatched at the same time.

## Considered options

**Raise the budget.** Rejected. It changes the threshold while the payload stays, and the
gate exists to catch exactly this.

**Move the bulk array to a `resource_link`.** Rejected on the recompute blocker above, which
is structural. Three further blockers exist — no result field can serve as a `uri_id_key`,
there is no calendar resource kind, and the bulk-resolution cross-check for a null id
argument is bound to a bucket id while the all-profiles read is cross-bucket — but those are
absent plumbing and would be addable. The recompute is not: it follows from resolution being
re-execution, so it cannot be fixed without persisting the computed result, which is a
different design.

**Strip schema metadata.** Splits into two very different proposals and must not be treated
as one. See D2 and D3.

**Reshape the profiles array.** Adopted, on structural grounds rather than arithmetic. See
D1.

## Constraints

Every figure below is a measurement taken at HEAD on 2026-08-05, with unreachable `$defs`
pruned after each removal. That pruning is load-bearing: a naive removal that leaves orphaned
definitions behind understates the recovery and produced a 19766 where the correct figure is
17378. Two independent workers disagreed on that number until the method was reconciled.

    baseline                          20589    headroom  -2589
    less the coverage commit          18972    headroom    -972
    less the recovery commit          18545    headroom    -545
    less both 2026-08-02 commits      16928    headroom   +1072
    titles suppressed                 17371    headroom    +629
    profiles removed                  17378    headroom    +622
    titles suppressed + profiles      14651    headroom   +3349

## Implementation

### D1 — Reshape `profiles` to a per-profile summary, on structural grounds

`OverviewCalendarResult.profiles` carries a full embedded calendar for every profile. It
becomes a summary — identifier, label, counts, next due — with the detail available through a
per-profile call.

**The reason is not that this gets under the budget, because it barely does.** Removing the
embedded calendar entirely reaches 17378, leaving 622 characters, and the summary that
replaces it costs some of that back. The reason is that the payload is over its real
allowance regardless. The 20589 decomposes as `$defs` 15844 plus roughly 4734 of envelope
spine — the shared success/error contract carried by every verb, which no payload change can
touch. **The verb-specific allowance is therefore about 13300, and this payload's definitions
alone are 15844.** The payload does not fit before the envelope is counted, and a reshape
designed against 18000 lands a result that still fails.

A design adopted because a number demanded it is hard to defend when the number moves. This
one is adopted because the full calendar for every profile does not fit a single tool
response and never did.

### D2 — Suppress pydantic auto-generated `title` keys, fleet-wide and on its own merits

Every `title` in this schema is a pure function of the key it sits under: 102 of 117 are
byte-identical to the auto-derived property name, and the remaining 15 are definition class
names identical to their own definition key, which a consumer resolving a reference already
holds. None carries information a consumer cannot compute.

Suppression recovers 3218 characters here and applies to all 297 verbs. The repository
already ships title-free schemas on the adjacent surface — tool **input** schemas carry zero
titles today and nothing has broken — so this brings the output side into line with the input
side rather than breaking new ground. No production code reads an output-schema property
title and no test asserts one.

**This is explicitly not the remedy for this verb.** It restores 629 characters of headroom
against a breach that cost 3661 — smaller by a factor of six — so one more afternoon of
comparable payload work would re-breach it. It is recorded here because the bytes are free
and the reasoning was developed here, not because it solves the problem.

**Status: this decision is pending an independent verdict.** The measurements are mine and
the self-attack is mine, which is precisely the combination that should not close a question.
Two specific gaps remain: whether an SDK or client path reads output-schema titles in a way a
repository search cannot see, and whether the suppression mechanism reaches every model in the
graph in one change or needs applying per nested model. The saving is measured; the
implementation cost is not.

### D3 — Do not strip `description`

Descriptions are 5068 characters here, and unlike titles they carry information an LLM
consumer uses. Removing them would shrink the schema and degrade the tool, and the
repository separately mandates the docstrings that generate them. That the gate measures them
is a known impurity in the instrument, not a licence to delete the content.

### D4 — Do not raise the budget

The ratchet's calibration is vindicated by the evidence: the payload measured 16928 before
the 2026-08-02 growth, comfortably under an 18000 ceiling set on 2026-07-08 "with headroom
above the current maximum". The instrument was right and was not being read.

## Rationale

**The breach was a conjunction, and this is the finding most likely to outlive the record.**
Two commits 24 minutes apart on 2026-08-02 — one adding obligation-coverage payloads, one
adding recovery payloads — jointly cost 3661 characters. Removing either alone leaves the
verb over budget (18972 and 18545); removing both drops it to 16928. **A bisect looking for
the one bad commit would have returned a clean bill of health from every commit it tested.**
Threshold regressions are exactly where bisection is most natural to reach for and exactly
where it cannot see the cause by construction. If you bisect a budget breach and every commit
comes back clean, the cause is a conjunction, not an illusion.

**Three compatible facts, recorded as three rather than collapsed into one.** The ratchet was
correctly calibrated; it was genuinely breached by real growth; and nobody saw for three days
because the lane carrying the gate had never run. Collapsing these produced two wrong readings
during the investigation — one that the payload had always been over and a newly-enrolled gate
merely surfaced it, and one that a single identified commit was the cause. Both were plausible
and both were wrong.

**No growth-rate claim is made and none is needed.** The verb's history shows three apparent
growth steps, but two were the verb being built out rather than accreting onto a settled
surface, so in the regime that matters there is one observation and one observation is not a
rate. The argument for treating 629 characters as thin rests on subtraction alone: the one
measured breach cost 3661, six times the margin that titles alone restore.

## Consequences

- `OverviewCalendarResult`'s registered schema changes, along with the all-profiles operator
  contract and documented-command conformance. That is a real cost and D1 accepts it.
- The per-profile detail becomes a second call. For an operator comparing profiles this is
  worse; for a schema that fits, it is the price.
- D2 is separable and should land or fail on its own evidence, not as part of this reshape.
- The verb-specific allowance of roughly 13300 applies to every verb, not just this one. Any
  future payload designed against the nominal 18000 is designing against a number 4700 too
  large.

### Two measurement traps this investigation hit, recorded so the next reader does not

`OverviewCalendarResult.model_json_schema()` measures 17558 and looks already under budget.
The gate measures the envelope-wrapped descriptor schema at 20589. Both are correct about
different objects, and checking the model directly returns a passing number for a failing
verb. This cost one worker half an hour.

A counterfactual that removes a property without pruning the definitions it orphans
understates the recovery — 19766 against a correct 17378 for the same operation. Prune
unreachable definitions from the root after any removal, or the remedy under test looks weaker
than it is.

### Limits of the evidence

The pre-growth figure of 16928 is a **reconstruction**: the models those two commits added
were removed from the current schema and unreachable definitions pruned. It is not a
measurement of the schema at that commit, which needs a checkout not available in this
worktree. The historical growth table underlying the shape discussion is an AST proxy for
schema bytes, not bytes.

Why two payload-growth commits landed 24 minutes apart without either author observing the
combined effect is not established. That the gate never ran is the likely explanation and has
not been confirmed against either author's local runs.
