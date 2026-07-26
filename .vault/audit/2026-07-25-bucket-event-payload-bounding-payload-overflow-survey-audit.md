---
tags:
  - '#audit'
  - '#bucket-event-payload-bounding'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - '[[2026-07-25-reconcile-evidence-relocation-adr]]'
---

# `bucket-event-payload-bounding` audit: `bucket-event payload value overflow survey`

## Scope

A full survey of production sites that bind a variable-length value to a
bucket-event payload key, undertaken to answer whether the substrate deserves a
standing guard against the shape.

The prior relocation record counted four occurrences and, at its
re-verification commit, concluded the tally stood at three closed and one live.
This survey re-derived the tally against the working tree rather than accepting
it, on the standing discipline that a count taken at an older commit is not a
measurement of the current one.

Semantic search was unavailable and its degradation is silent: the code index
held roughly 902 chunks against roughly 4,546 source files while reporting
`degraded_reasons: []`. Every statement below therefore rests on direct reads,
on `rg`, and on execution against the real model — never on a search miss.

## Findings

### payload-overflow-tally | high | the shape has six occurrences, not four

Two live occurrences were found that no prior pass had recorded, both in
`src/cadrumo/application/ledger/_actions_split_merge.py`: the split event bound
`child_transaction_ids` to a comma join of the child ids, and the merge event
bound `source_child_ids` to a join of the same. Both are live in shipped verbs.

Together with the four already recorded — the ledger-export overflow, the
`ledger reset` overflow, the reconcile diff detail, and the joined pair in the
transaction-removal event — the shape has occurred six times.

### split-merge-overflow-threshold | high | an eight-way split cannot record its own event

A transaction id is a lowercase SHA-256 digest of 64 characters, so eight
joined on commas is 519 characters against a 500-character payload slot. This
is the identical arithmetic to the transaction-removal defect fixed earlier
against attachment ids.

The threshold was confirmed by execution rather than by arithmetic alone.
Constructing the real event model with progressively larger cohorts, the
refusal falls on the joined key at exactly eight children: seven children
(454 characters) pass that key, eight (519) and ten (649) are refused on it.

The verb imposes no upper bound on the cohort — it requires at least two
children and nothing else — so an eight-way split of a consolidated payment is
ordinary use rather than a pathological input.

### remedy-was-already-adjacent | high | the missing ingredient is detection, not knowledge

Both new occurrences already carried `child_count` immediately beside the join,
exactly as the transaction-removal payload already carried `cascade_count`. In
every case the correct remedy sat on an adjacent line and was still not
applied.

This is the finding that bears on whether a guard is warranted. The failure is
not that the remedy is unknown or costly; it is that nothing identifies the
shape at the moment the line is written.

### discovery-record-evades-deliberate-recount | high | attention is not containing the class

None of the six occurrences was found by a pass looking for it. They surfaced
while fixing an export, while fixing a reset, while measuring a Modelo 100
reconcile, and — for the two recorded here — while ruling on whether the
previous four justified a guard.

Decisively, the pass that re-verified the tally and concluded that the pattern
had "resolved itself around the exception" was examining this exact shape and
still missed two live instances. That conclusion is falsified. The facts that
record states were true when written; only the inference drawn from them fails,
and it fails for the reason the record itself gives, having been written
without reliable search.

### gate-unproven-until-it-bites | high | two gates in one session reported safety they did not provide

Two independently authored gates in this campaign were false green, and neither
failure was visible by reading the test.

The reconciliation store's first atomicity test stayed green when the production
co-emit was split into two sequential saves. It built its own writes and
exercised the batching primitive rather than the code composing it, and nothing
observable on the success path distinguishes one batch from two. It failed open
— the test was wrong while the production code was correct — so a later
regression would have shipped unnoticed.

The payload gate recorded here returned clean against the very file whose
overflow prompted the work. It matched payload dicts passed inline as a keyword
while the reconcile payload is built into a local and passed later, so it
reported safety about the single case it was built for.

Both were found the same way and by no other means: by making the production
code wrong on purpose and checking whether the gate noticed. Inspection did not
find them, and in both cases the authors had read their own tests closely.

### unratified-cap | medium | the bound had no declared home

The 500-character cap was an inline literal in the domain model. No record
ratified the figure, while one record designed against it as a given. A
producer had to infer the bound by reading a constraint in a model file, and a
guard cannot enforce a bound that is not named.

### scoping-noise | medium | an unscoped detector is dominated by false positives

A first cut keyed on the name `payload` alone flagged twenty-two values, of
which twenty-one were not bucket events: Google Sheets rows, LLM telemetry and
cache records, CLI result bodies, and rendering payloads. `payload` is a common
name across the codebase and carries no capped-slot contract outside this
substrate.

Scoping the detector to modules that actually build bucket events, and treating
fixed-width renderings as bounded, reduces the flagged set to exactly the real
occurrences. Measured across the whole production surface, only a small number
of distinct call kinds ever appear as a bucket-event payload value, and each is
provably fixed-width — so an allowlist is affordable rather than a swamp.

### two-spellings | medium | a keyword-only matcher misses a real occurrence

Payload dicts ship in two spellings: passed inline as a `payload=` keyword, and
built into a local and passed later. The reconcile occurrence uses the second,
so a first cut of the detector keyed only on the keyword form returned clean
against the very file whose overflow prompted the survey. A detector that
recognises one spelling reports a false negative on the other.

## Recommendations

Rule on whether the substrate carries a standing guard. The decision belongs in
a follow-on ADR and is not taken here; the evidence bearing on it is the
discovery record above rather than the occurrence count alone.

Close the two live occurrences with counts. Every split child carries a
required `split_group_id` and both events already carry that group id, so the
cohort stays recoverable from the transaction catalogue and a count loses
nothing — the same justification the transaction-removal fix recorded, which
holds here on its own terms rather than by analogy.

Give the cap a declared home with a stated contract, so a producer can read the
bound and the sanctioned alternatives without inferring them from a model
constraint.

Should a guard be ruled in, keep its exemption list self-expiring: an exemption
that outlives the site it excuses is a hole, and this survey found the reconcile
exemption went stale within the hour as the relocation work landed.

Treat a new gate as unproven until it has been shown to bite on a deliberate
regression of the thing it guards. Restore from a copy taken beforehand; never
reach for a destructive git operation to undo the regression. This is the only
technique that found either false green recorded above, and it costs minutes
against a gate that would otherwise report safety indefinitely.

The corollary is about where the risk sits once a gate does bite. A gate that
cannot prove a value bounded and therefore flags it is behaving correctly; the
judgement moves into the allowlist, where each entry asserts something the
detector cannot see. So the allowlist is what a future reviewer must read, not
the detector. An entry that earns its place states why the value cannot grow; an
entry added to quiet a flag is the regression this guard exists to prevent, and
it will look identical in the diff.
