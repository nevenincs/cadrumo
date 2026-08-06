---
tags:
  - '#adr'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:803bf42ce9b136adf50f34a95fab98b725f79a67903e5a7404c5c3d05710e19d'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
  - '[[2026-08-05-ci-lane-deconflation-step-check-attribution-audit]]'
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

## Amendment (2026-08-05): D2 is confirmed, and two of its supporting claims were wrong

The independent verdict D2 was pending has arrived. **The decision survives on substance and
could not be broken** — but two of the claims supporting it were wrong, one of them the
load-bearing one, and one framing in this record is withdrawn.

**D2's load-bearing argument is void; strike it.** This record argued that the repository
already ships title-free schemas on the adjacent surface, tool input schemas carrying zero
titles, so suppression merely brings the output side into line. That is false as reasoning.
Input schemas are built by walking the live command tree; the model-schema generator appears
nowhere in that path, so nothing was ever suppressed there and nothing was ever observed not
to break. It is an absence of evidence, not evidence of safety. The claim does not need it.

What replaces it is stronger and was read from the SDK source rather than inferred from a
repository search: the client session uses the output schema **only** to compile a validator
for structured content, and JSON-Schema `title` is a pure annotation with no validation
effect. Every `title=` in the SDK is the protocol-level display name for a tool, resource or
prompt — a different field entirely.

**The census is 115 of 117, not all of them.** Two property titles are not pure functions of
their key: `result` carries `OverviewCalendarResult` and `error` carries `ErrorEnvelope`,
model names not computable from `result` or `error`. Materiality is low — nothing reads them
and the model is derivable from the command key — but this record's "none carries information
a consumer cannot compute" is false as written, and a claim of universality that is 98% true
is still a wrong claim.

**The framing "the gate stops being forced" is withdrawn, and its replacement is the point.**
The gate's own docstring names its target: output-schema size as the static proxy for the
structured content a verb emits. Titles never appear in structured content. So suppressing
them reduces the proxy **without reducing the target** — by the gate's stated purpose that is
gaming it, which is the same shape as the metadata rejection D3 already refuses. The honest
statement is narrower and better: **the gate stops firing; the thing it exists to bound is
unchanged.** If suppression incidentally drops this verb under the line, that has revealed
the proxy is imperfect, and the response is to fix the instrument to measure emitted content
rather than to note that the proxy now passes.

D2 therefore stands as a decision on a **different axis** from the budget. The schema really
is emitted at `tools/list` once per session, and suppression saves a measured 198,806
characters across all 297 verbs — about a tenth of total output-schema bytes, with zero verbs
over budget afterwards. Worth doing on its own merits; not to be recorded as satisfying the
budget. That separation is the whole reason D2 was written as separable.

**The composition argument is sharper than the one D1 used.** Both remedies are required, and
the decisive number is not this record's six-times comparison. On 2026-08-02 the payload sat
at 16928 with 1072 characters of headroom, and two commits 24 minutes apart consumed all of
it. **So the 629 that titles alone restore is less than a headroom that already proved
insufficient three days ago.** Either remedy alone re-trips on the next payload model; both
together give 3349.

**One open question of this record is now closed.** Suppression is a post-process strip in the
output-schema builder, reaching the whole graph including all 13 definitions in one place —
no per-model configuration, no nested overrides, no maintenance surface. The implementation
cost is known, not projected.

**The blocker split holds with one refinement.** The recompute remains structural, confirmed
against the source: the calendar is computed from a clock with no persisted record, and
resolution is scoped to encrypted persisted state, so a link resolved later can return rows
the call never summarised. Two of the remaining three are ordinary plumbing. The third — the
bulk-resolution cross-check bound to a bucket id — is plumbing **with a safety review
attached**: it exists so a link cannot silently resolve a different bucket's rows, so
generalising it for a cross-bucket read means redesigning a safety check rather than widening
a signature. Record it as contingent-but-not-cheap; this record's "absent plumbing and would
be addable" understates it.

**One prior objection is now historical and belongs in the past tense.** Thinning used to
inflate: the helper built its alternative branch from two full copies of the property body,
so a schema whose definitions stayed reachable from another property paid the duplication and
saved nothing — which is why thinning any non-profiles array took this verb to roughly 22400.
That is fixed; the bodies are declared once and only the discriminator sits in the
alternation, and all four thinned verbs shrank. A reader proposing thinning again will no
longer inflate. The same fix closed a latent hole where branch disjointness relied on models
forbidding extra properties: this verb allows them and carries a non-required profiles array,
so it would have hit it.

**Two questions stay open and are recorded as open.** Third-party MCP clients outside this
repository may render property titles in a form generator; the SDK in this environment was
verified and every client was not. If one does render them, "recomputable from the key" stops
being sufficient — though it would be rendering a title the server has never guaranteed, and
the input schemas such clients build forms from have never carried one. And no authoritative
specification statement on titles in output schemas was located, so the SDK's behaviour is
the evidence here, not the spec text.

### The two title censuses reconcile exactly; the disagreement was grouping

Two independent counts of the same 117 titles were reported as 102 plus 15 and as 104 plus
13, and the difference looked like a measurement discrepancy worth recording as unresolved.
It is not one. Measured: 102 property titles auto-derived from their key, 2 property titles
carrying a model name (`result` and `error`), and 13 definition titles identical to their
definition key. 102 + 2 + 13 = 117.

The first count grouped by DERIVABILITY, folding the two model-named titles in with the
definition titles as "not auto-derived". The second grouped by LOCATION, folding them in with
the properties. Both are correct and both describe the same partition. Recorded because an
unreconciled count in a decision record invites a later reader to re-measure, and because it
is the same lesson this record already carries about orphaned definitions: two measurements
that disagree usually differ in their setup rather than in the fact they measure.

## Amendment (2026-08-06): both decisions are implemented, and the criterion that mattered is met

Measured at HEAD:

    total 15896   (was 20589, budget 18000)
    $defs 11533 across 11 definitions   (was 15844 across 13)
    envelope 4352   (was ~4734)
    titles present: 0

**D1 landed.** The per-profile summary replaced the embedded calendar, and two definitions
left the graph with it.

**D2 landed and is no longer pending.** The independent verdict arrived and survived, with two
of its supporting claims struck; the suppression is now implemented and the schema carries
zero titles. The envelope shrank as a side effect, which is the fleet-wide half of that
decision showing up in this verb.

**The criterion this record actually set is met, and it is not the budget.** This ADR argued
the payload was over its REAL allowance — roughly 13300 once the shared envelope is subtracted
— while its definitions alone were 15844. Definitions are now 11533, under that allowance with
about 1800 to spare. Had the reshape been designed against the nominal 18000 it would have
landed something that passed the gate and stayed over its allowance; it was designed against
the smaller number and cleared both.

Worth stating because the two are easy to confuse in a later reading: passing at 15896 against
18000 is the gate going green, and 11533 against ~13300 is the payload actually fitting. This
record cared about the second.

**One prediction of this record was wrong in the safe direction.** It expected the summary to
cost back some of the 622 characters that full removal of the embedded calendar would recover.
The landed result is better than the floor this ADR computed — 11533 of definitions against a
17378 whole-schema floor for outright removal — because the composition with title suppression
recovered more than either remedy measured alone, as the composition table predicted.
