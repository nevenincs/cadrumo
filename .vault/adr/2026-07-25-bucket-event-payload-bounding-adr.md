---
tags:
  - '#adr'
  - '#bucket-event-payload-bounding'
date: '2026-07-25'
modified: '2026-07-26'
body_hash: 'sha256:ed23a3051fab09d42e9107e72618f56164142d4495614982cb78d9cac66d98d7'
related:
  - "[[2026-07-25-reconcile-evidence-relocation-adr]]"
  - '[[2026-07-25-bucket-event-payload-bounding-payload-overflow-survey-audit]]'
---

# `bucket-event-payload-bounding` adr: `bounding a bucket-event payload value` | (**status:** `accepted`)

## Problem Statement

A bucket-event payload value is capped, and the cap is enforced by refusal
rather than truncation. A producer that joins a collection into one value
therefore acquires a silent ceiling on how large that collection may grow;
past the ceiling it cannot record its own event at all, because the write
raises before anything is saved.

`2026-07-25-reconcile-evidence-relocation-adr` counted four occurrences of
this shape, closed three by hand, and carried the remaining question — whether
the substrate deserves a standing guard — as the last systemic item. This
record answers it.

The question is not whether each occurrence can be fixed. All of them can, and
the remedies are known and cheap. The question is why a shape with a known,
cheap remedy keeps reaching production, and whether anything in the substrate
should stop the next one.

## Considerations

- The relocation record concluded, at its re-verification commit, that the
  tally stood at three closed and one live, and that "the pattern has resolved
  itself around the exception". **That conclusion is falsified.** Two further
  live occurrences were found in `application/ledger/_actions_split_merge.py`:
  the split event joined `child_transaction_ids`, and the merge event joined
  `source_child_ids`. Neither had been found by any prior pass, including the
  pass that re-verified the tally and declared the pattern resolved.
- The two new occurrences carry the identical arithmetic to the
  transaction-removal defect that was fixed by hand: a transaction id is a
  64-character SHA-256 digest, so eight joined on commas is 519 characters
  against a 500-character slot. Measured against the real model, the refusal
  falls on the joined key at exactly eight children. The split verb requires at
  least two children and imposes **no upper bound**, so an eight-way split of a
  consolidated payment is ordinary use, not a pathological input.
- So the count is six, not four, and the discovery record is what matters: each
  was found by a different pass, none by the pass looking for it, and two
  survived a re-verification whose explicit purpose was to recount them. A
  defect class that evades a deliberate recount is not being contained by
  attention.
- The remedy is not the missing ingredient. Both new occurrences already
  carried `child_count` immediately beside the join, exactly as the
  transaction-removal payload already carried `cascade_count`. In every case
  the fix sat adjacent to the defect and was still not applied. What is missing
  is **detection**, not knowledge.
- The cap is legitimate and must stay. The event log is a substrate every
  service writes to, so one unbounded producer degrades a shared surface rather
  than only its own. Raising it trades a bounded local refusal for unbounded
  global growth, and no larger constant bounds the real payloads either.
- Refusal rather than truncation is also correct and must stay: a silently
  shortened audit value is worse than a refused write. That choice is precisely
  what converts an unbounded producer into a hard ceiling, which is why the
  authoring-time shape matters.
- The cap had no declared home. It was an inline literal in the domain model,
  no record ratified the figure, and one record designed against it as a given.
  A guard has to name the bound to enforce it, so this record gives it one.
- The occurrences are not homogeneous, and a single remedy would be wrong.
  Where the joined members stay recoverable from their own catalogue, a count
  loses nothing. Where the event log is the only copy, a count is lossy and the
  detail needs a durable home instead — the reconcile case, ruled separately.

## Considered options

- **(a) Close the sixth occurrence and leave the shape unguarded.** Rejected.
  This is what was done five times. The two occurrences found here are the
  measured cost of it, and they were found by accident while ruling on
  something else.
- **(b) Raise or remove the cap.** Rejected, on the relocation record's
  reasoning, unchanged: the substrate is shared, and no larger constant bounds
  the real payloads.
- **(c) Truncate silently at the boundary.** Rejected. It converts a loud
  refusal into quiet audit-evidence loss, which is strictly worse on a
  filing-grade surface.
- **(d) A runtime check in the emitter.** Rejected as the primary guard. It
  fires at the same moment the pydantic refusal already does, so it improves
  the message and nothing else — the producer has still already been written,
  reviewed and shipped. It is worth having as a producer-side convenience, and
  is adopted in that reduced role.
- **(e) A static gate that refuses an unbounded value bound to a payload key,
  plus a declared home for the cap.** Adopted. It moves discovery to authoring
  time, which is where all six occurrences should have been caught and where
  none of them were.

## Constraints

- The gate must be a **shape** check, not a length check. The length is not
  knowable statically; the defect is binding an unbounded collection to a
  bounded slot, whatever today's cardinality happens to be.
- It must be scoped to bucket-event payloads only. `payload` is a common name
  for Sheets rows, LLM telemetry and CLI result bodies, none of which are
  written into the capped slot and none of which this gate has any business
  bounding. An unscoped first cut flagged twenty-two values, of which
  twenty-one were not bucket events at all.
- It must recognise both spellings that ship: the value passed inline as a
  `payload=` keyword, and the dict built into a local and passed later. A
  keyword-only matcher misses the second, which is how the reconcile occurrence
  evaded a first cut of this very gate.
- It must not become an exemption swamp. Measured across the production
  surface, the sanctioned-remedy allowlist needed to reach zero false positives
  is small and every member is provably fixed-width, so the gate is affordable.
- It must be able to fail. A shape gate whose matcher never matches, or that
  scans a surface it cannot parse, passes silently and forever.

## Implementation

Ruled `accepted` on option (e).

**The cap gets a declared home.** `BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH` in
`domain/buckets/_event.py`, exported through the package facade and consumed by
the payload-value constraint rather than restated beside it. Its docstring
carries what no record previously held: that a payload value is a fixed-width
fact and never a variable-length join, the arithmetic that makes eight joined
identifiers overflow, and the three sanctioned alternatives — a **count** when
the members are recoverable from their own catalogue or from sibling events in
the same batch, a **digest** when the set must stay verifiable but need not be
enumerable from the log, and a **durable home of its own** when the event log
is the only copy.

**The producer-side helper.** `payload_value_fits` answers the bound without
constructing an event, so a producer can check before it builds rather than
discovering the ceiling as a validation error raised after the surrounding work
is done. This is option (d) in its reduced role.

**The gate.** `domain/buckets/tests/test_payload_value_bounding.py` walks the
production surface and flags any value bound to a payload key that it cannot
prove bounded — a join no digest wraps, or a call outside a small allowlist of
fixed-width renderings. It is scoped to modules that actually build bucket
events, and it recognises both the keyword and the assigned-local spelling.

Exemptions are keyed by file and payload key and must state a reason. Two
companion tests keep the allowlist honest: one refuses an exemption without a
stated reason, and one refuses an exemption that outlives the site it excuses,
so an entry expires automatically when its line is fixed. That ratchet fired
during this work — the reconcile exemption went stale within the hour, as the
relocation removed the line it excused.

A detector-liveness test pins the matcher against each known offence shape and
each sanctioned remedy, and a surface test pins that the scan inspects a
non-empty production surface, so a green run is evidence the surface is clean
rather than evidence the detector is dead.

**The two live occurrences are closed in the same change**, with counts. Every
split child carries a required `split_group_id` and both events already carry
that group id, so the cohort stays recoverable from the transaction catalogue
and the count loses nothing — the same justification the transaction-removal
fix recorded, and one that genuinely holds here rather than being imported by
shape.

## Rationale

The knockout is the discovery record, not the occurrence count.

Six occurrences would be unremarkable if each had been found by the pass
looking for it. None was. They surfaced while fixing an export, while fixing a
reset, while measuring a Modelo 100 reconcile, and — for the two found here —
while ruling on whether the previous four justified a guard. The pass that
re-verified the tally and concluded the pattern had resolved itself around a
single exception was looking directly at this shape and still missed two live
instances in a shipped verb.

That is the argument. A defect class that survives a deliberate recount is not
being contained by attention, and the remedy is not more attention. Both new
occurrences already carried the correct fix as an adjacent line, which settles
what the missing ingredient is: not knowledge of the remedy, not willingness to
apply it, but any mechanism that says *this is one of those* at the moment the
line is written.

The honest counter-argument is that a static shape gate cannot prove a helper's
return value is bounded, so it trades false negatives for an allowlist that
could rot. Two things answer it. The allowlist was measured rather than
assumed: across the whole production surface only a handful of distinct call
kinds appear as payload values, and each is provably fixed-width. And the gate
is deliberately conservative in the safe direction — an unrecognised call is
flagged, so a new helper must be examined and named rather than silently
trusted.

The gate does not make the cap safe. It makes the shape visible at the moment a
reader can still choose between a count, a digest, and a durable home. That is
the choice all six occurrences got wrong, and the only one of the three that
needed a decision record got one separately.

## Consequences

The next join into a payload value fails at authoring time with a message
naming the three alternatives, instead of reaching production and being found
by a later pass looking for something else. The cap acquires a declared home
and a stated contract, so a producer no longer has to infer the bound from a
literal in a model file.

The cost is a static gate with an allowlist, and an allowlist is a maintenance
surface that can rot. The two companion tests bound that: an exemption without
a reason fails, and an exemption that outlives its site fails. A new bounded
helper will occasionally need to be added to the allowlist, and that is the
intended friction — the addition is where a reader confirms the value really is
fixed-width.

The gate proves a shape, not a length. A helper that returns an unbounded value
but is named in the allowlist would pass, so the allowlist entries are
load-bearing and must stay honest. This is a weaker guarantee than a runtime
bound and is deliberately chosen: the runtime bound already exists and already
fires — too late to be useful, which is the whole problem.

Two consequences are recorded honestly rather than argued away. This record
falsifies a conclusion of the relocation record it descends from; that record's
*facts* were true when written, and only the inference drawn from them — that
the pattern had resolved itself — fails, for exactly the reason it gives, since
it was written without the ability to search reliably. And the reconcile
occurrence remains the one case bounded metadata cannot close, which the
relocation ruling already settled; nothing here reopens it.
