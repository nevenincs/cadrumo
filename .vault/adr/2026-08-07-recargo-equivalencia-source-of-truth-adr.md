---
tags:
  - '#adr'
  - '#recargo-equivalencia-source-of-truth'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a2c28ca221bba03230266c64c597995b79f5d925fdd2280089da1768e66ea14f'
related:
  - "[[2026-08-07-recargo-equivalencia-source-of-truth-research]]"
---

# `recargo-equivalencia-source-of-truth` adr: `the invoice or the table: what establishes a recargo de equivalencia cuota` | (**status:** `proposed`)

## Problem Statement

A recargo de equivalencia cuota can be established two ways, and this project has never
chosen between them. Today the supplier's figure is copied from the transaction to the
return with nothing checking it, while a grounded rate table sits beside that path with
no consumer. Neither arrangement was decided; both are what happened.

A decision is needed now because two pieces of work are waiting on it and one of them is
a live defect. The Modelo 303 recargo block carries a cuota under the wrong rung, and the
repair for it will either derive a rate or reference one. Separately, the transitional
recargo rates published for 2023 and 2024 are now grounded in bundled corpus, so the
question of whether they belong in the table has become answerable where it was
previously deferred as ungrounded. Extending the table before choosing would author data
that nothing reads, into a structure that cannot hold it, under a citation that looks
authoritative -- see `2026-08-07-recargo-equivalencia-source-of-truth-research`.

## Considerations

- The supplier charges the recargo and the invoice records it, so the invoice is the
  document of record for that transaction; the research finds the shipped path already
  treats it that way, by omission rather than by decision.
- This codebase refuses to overwrite a recorded external fact with a computed one
  elsewhere, and a derived recargo would do exactly that.
- An operator entering a wrong recargo today produces a wrong return with no signal.
- AEAT prints each recargo rung's Tipo as a record-design constant, so a mismatch between
  the declared base and cuota is arithmetically detectable from the filed record without
  any audit -- the same property that makes the Modelo 303 rung mis-allocation catchable.
- The rate table has no production consumer at all, so choosing derivation would be a
  wiring decision rather than a switch-over: nothing currently depends on its answers.
- The table's key shape cannot express the transitional rates, independently of this
  decision.
- The application never files. A defect that survives export reaches the taxpayer with no
  gate behind it, so a signal the operator can act on is worth more than a silent
  correction they cannot see.

## Considered options

**Derive the cuota from the grounded table.** Catches a wrong operator entry and matches
how AEAT publishes the rate. Rejected as the primary rule: it overwrites the invoice,
which is the legal document of record, and a supplier's genuinely unusual figure would be
silently replaced by a computed one.

**Keep the operator's figure authoritative and use the table for nothing.** The status
quo. Rejected: it leaves the wrong-entry case entirely unguarded, and leaves a grounded
table in the tree with no purpose, which reads to a later author as an unfinished wiring
job rather than as a decision.

**Keep the invoice authoritative and use the table as a validation reference, surfacing
an advisory on mismatch.** Recommended, and marked as a recommendation rather than a
finding: everything else in this record and its research is measured, this is judgement.
Preserves the document of record, gives the wrong-entry case a signal, and gives the
table a defined job. Costs an advisory channel and a re-keyed lookup.

**Refuse on mismatch rather than advise.** Rejected: a legitimate invoice can carry a
figure the table does not predict, and refusing would block a correct filing on a correct
invoice.

## Constraints

The rate table cannot be extended in its present shape under any option this record may
choose. Its lookup is keyed on the IVA tier with no date, and the research establishes
that one tier carries two recargo rates simultaneously inside the 2023 to 2024 window.
Re-keying the lookup on the applied rate and the operation date is a precondition of the
table being used at all, not a consequence of choosing derivation. This binds even if
this record is rejected outright.

The table has no production consumer today. That is recorded as a measured fact because
its grounded, complete-looking state otherwise invites the assumption that it is
load-bearing.

The table's grounding depends on two catalogue entries that are agent-prepared and carry
an outstanding filing-grade operator review. This record does not rest on human-reviewed
grounding and must not be read as doing so.

Whether a zero-rated supply carries a recargo of zero or no recargo at all is a distinct
semantic question, tracked separately. It is not settled here, and neither option above
depends on its answer.

## Implementation

The transaction's recargo figure remains the value that reaches the return. Nothing in
the aggregation path changes its provenance.

The rate lookup is re-keyed to answer from the applied IVA rate and the operation date
rather than from the tier alone, and is populated with the ordinary article 161 rates
plus the transitional rates the research grounds. That re-keying is required regardless
of what consumes the result.

A validation step compares the operator's figure against the rate the table resolves for
that applied rate and date. Where they disagree it emits a non-blocking advisory through
the typed notice channel, naming both figures and the provision the expected rate comes
from. Where the table resolves no rate for that combination it stays silent rather than
guessing, because an unmodelled window must not read as a mismatch.

The advisory is a diagnostic, not a correction: the filed figure is unchanged whether or
not it fires.

## Rationale

The knockout against derivation is that the invoice is the legal document of record and
the recargo is a charge the supplier actually made. A computed figure that disagrees with
a real invoice is wrong about that transaction however well grounded the computation is,
and this project's standing posture is to preserve the recorded fact and surface the
discrepancy rather than resolve it silently.

The knockout against the status quo is that it has no reader. A grounded table nothing
consults is indistinguishable from an unfinished job, and the research shows this one has
already survived long enough to be mistaken for load-bearing.

The advisory shape wins because it is the only option that leaves both quantities true:
the filed figure stays the one the supplier charged, and the operator learns when it
departs from the published rate. It is the same posture the surrounding screens settled
on -- surface, do not override, do not silently accept -- so choosing it keeps one rule
across the surface rather than a special case for recargo.

## Consequences

The rate table gains a defined purpose and a consumer, which makes its correctness
matter. Today an error in it would be undetectable, because nothing reads it.

Operators gain a signal on a class of error that is currently silent. It fires on the
supplier's data rather than on their own, which may read as noise until the mismatch
cases are understood, so the advisory must name the provision or it will be dismissed.

The re-keying is a prerequisite and is not free: consumers of the tier-keyed lookup must
move to the applied-rate form. There are none today, which makes this the cheapest moment
to do it, and argues for doing it whether or not the advisory is built.

Choosing the invoice as authoritative forecloses using the table to repair historical
rows. Where a filed return carried a wrong recargo, this decision surfaces it going
forward and does not correct it retrospectively.
