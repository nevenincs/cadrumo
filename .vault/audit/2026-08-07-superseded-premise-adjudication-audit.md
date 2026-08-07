---
tags:
  - '#audit'
  - '#superseded-premise-adjudication'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0ad57b8957a04a1129d5846310a4c040ad0b605af2971de2f5e599c49a4be533'
related: []
---
# `superseded-premise-adjudication` audit: `Adjudicating the four unresolved superseded-premise findings`

## Scope

A prior coordination-fleet sweep of a session's running findings distinguished
two classes that look identical on a board and have opposite urgency: a DEAD
PREMISE (the fact a finding rests on is now false; closing it is free) and a
SUPERSEDED CONCLUSION over a LIVE PREMISE (the measurement still holds, only
the ruling was overtaken; the finding must not close, because its measurement
is the only place that fact is written down). That sweep confirmed one dead
premise and two premises invalidated by a later ruling, and flagged four more
findings as needing adjudication without running it. This audit closes that
adjudication for those four, re-verified against HEAD rather than against
each finding's own account of HEAD, and records the shape of what it found
because the shape is the more durable lesson than any single outcome.

Findings are cited by their code locators. The coordination-fleet task board
itself is out of scope for citation here — it is ephemeral session state, not
a project record — so this document is the durable home for the one fact
that would otherwise exist nowhere else: the `[700]`/`[701]` box
reconciliation.

## Findings

### zero-dead-premises-among-the-four | high | the distribution itself is the finding

None of the four flagged findings turned out to be a dead premise, and none
needed a title rewritten to stop reading as open work. Two had already
completed their own honest follow-through before this adjudication ran; one
required a genuinely new reconciling sentence that existed nowhere; one had
already resolved itself entirely in the gap between being flagged and being
adjudicated. That is a materially different distribution from the earlier
sweep's three confirmed-stale records, and treating all seven as one
undifferentiated bucket would have been the wrong record. The class
distinction the original sweep drew is real, but a third outcome is common
and under-named by that taxonomy: a finding can be neither dead nor
superseded, only unverified since it was last touched.

### a-board-sweep-can-go-stale-between-writing-and-acting | high | the meta-finding

Two of the four findings — the export-representable-set gate and its sibling
expressiveness gap — were already closed with real, HEAD-verified adjudication
text by the time this pass began, even though the sweep that flagged them as
needing adjudication had been written against an earlier state of the board.
Both findings' own text cited a closing change (`core.ExportExemptionReason`,
declared in `src/cadrumo/core/_export_exemption_reason.py`) and the two
commits that shipped it; both commits were confirmed ancestors of HEAD before
trusting the citation.

This is the same failure class the sweep itself was chartered to find, one
level up: a record describing the board is accurate when written and can go
false before it is read, with nothing inside the record to signal which. A
task board under active multi-agent write pressure moves faster than any
single sweep of it. The corollary is procedural rather than a one-time fix: a
sweep of a live board must re-verify at ADJUDICATION time, never trust its
own or a peer's snapshot from AUTHORING time, however recent. Checking the
two "already completed" labels against HEAD rather than accepting them is
what surfaced this; skipping that check would have produced a report that
re-stated stale work as a live gap.

### rate-box-700-701-are-orthogonal-not-competing | medium | reconciled, durably recorded here

Two findings named box identities for Modelo 390's ordinario 0% tier without
stating whether they agreed: one held that box `[700]` is the tipo (rate)
declaration and is correctly bound; the other, closing a separate guard
against a row asserting an internally contradictory rate/cuota pair, named
box `[701]` explicitly as "Reg. ordin. Tipo 0% Cuota" — the cuota box for the
same tier — and proved that once the contradiction guard exists, `[701]` can
only ever carry zero, because a zero-rate row can only produce a zero cuota.

These are not competing identities for one slot; they are the rate half and
the cuota half of the same tier, on two different registry axes, and the
proof that `[701]` is structurally pinned to zero means no live figure can
ever surface a disagreement between the two. Nothing in either finding was
wrong; the board simply never stated the reconciliation, which is why it read
as an open question. Recorded here rather than left in task-board metadata,
because a fact two records could otherwise disagree about indefinitely
deserves a home that outlives the session.

### design-registry-gate-direction-self-corrected | low | verified current, no correction needed

A finding proposing a number-keyed cross-check gate between Modelo 390's
bundled AEAT record design and the registry (originally citing "311 false
positives" as the reason the gate was premature) had already re-derived its
own figures after a later change rewrote design enumeration, producing a
different count (343) through a different parser, and explicitly refused to
treat the two counts as comparable because they came from different
extractions of "the boxes in a design." It also flagged, unprompted, the one
number it had inherited that had NOT been re-derived and should be treated as
stale. The landed commit and the docstring it cites in
`src/cadrumo/domain/calculations/registry/_record_design_coverage.py` were
both confirmed present at HEAD. The finding's reasoning is current; only its
task-board status field was wrong, which is bookkeeping rather than a
premise problem.

### design-enumeration-duplicates-honestly-routed | low | verified current, remainder is deliberate

A finding on three byte-identical Modelo 390 record-design PDFs proposed
deleting them as duplicates, and a fuller measurement found the real defect
was upstream: three consumer functions in
`src/cadrumo/domain/calculations/registry/tests/test_revision_span_matches_published_designs.py`
each collapse a year to one design, silently discarding a second design AEAT
published mid-year. That fuller measurement's own follow-up finding recorded
what landed (a widened attribution function, confirmed present at HEAD
alongside the three still-single-per-year functions it describes) and
deliberately left the consumer migration undone, routing it to whichever
author owns the span gate rather than closing it unilaterally — because
migrating those three functions changes what the gate's boundary comparison
means, and that decision belongs to the gate's existing owner. Nothing here
needed correction; the deliberate remainder was already tracked honestly
rather than silently dropped.

## Recommendations

None of the four findings needs further action from this audit. The one
durable artefact this campaign produces is the `[700]`/`[701]` reconciliation
above, now recorded outside ephemeral session state.

The corpus and the coordination-fleet board beyond the four findings named
here remain unswept, not clean — this audit adjudicates exactly the four
flagged findings and does not extend to any other open item, including the
two findings this campaign explicitly left with their owners.
