---
tags:
  - '#audit'
  - '#unstructured-document-ingestion'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ab1c8a575b5fde7052df9cdbf2e7472e758962a3709e62a7e96b7c2084f3b5fc'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
  - "[[2026-08-13-unstructured-document-ingestion-record-gap-close-audit]]"
---

# `unstructured-document-ingestion` audit: `what the campaign closed without, read as an inheritor`

## Scope

The close rule requires a fresh-context honesty review against the closure
summary BEFORE structural completeness is declared, and requires that a campaign
not narrow its own completion criterion without writing what the standing goal
still asks for that the narrowing excludes.

This is that review, taken as someone inheriting the tree and reading the claim
"306 of 306, complete" against what is actually there. The sibling record-gap
audit answers whether each closed row was built. This one asks the different and
harder question: **what did the campaign close WITHOUT.**

## Finding 1 -- the governing ADR's own named open question is still open

The ADR names exactly one question as measurable rather than decided:

> whether a low-context model extracts better over fewer fields per call than
> all fields at once. It has architectural consequences for S2's call shape and
> is resolved by the D9 harness at the design-target tier, never by assertion.

The campaign closed at 306 of 306 **without answering it**, and the closing row
says so in its own text rather than obscuring it: the driver is built, the
structured lane runs deterministically over the pinned corpus, and *what the
ADR's question still needs is a model-lane run* -- a runtime the operator
supplies, not code anyone writes.

**This is honest, and it is still a narrowing.** What the standing goal asks that
the closure excludes: the ADR made a call-shape decision contingent on a
measurement, so S2's call shape currently rests on the design's assumption rather
than on the evidence the ADR said would settle it. Nothing downstream is wrong;
the architectural choice is simply unvalidated in the one respect its own record
said must not be taken by assertion.

The instrument is real and the blocker is precise -- an inference runtime with a
low-context model pulled. That is a smaller and more actionable carry-forward
than "unmeasured", and it is the correct place for it to have landed.

## Finding 2 -- the closure summary claims nothing the tree does not support

Every one of the 34 record-less closures was verified against HEAD in the sibling
audit, and none was unbuilt, narrowed or recorded-but-not-implemented. Two are
delivered beyond their row. On the declarative-versus-action axis this campaign
reads clean: the checkboxes are not the problem.

## Finding 3 -- one row was previously found closed against its own record, and
that is the pattern worth carrying

Earlier in this campaign a row had been retired while its own orphaned execution
record said the step was never delivered. It was restored as `W04.P10.S333`,
rebuilt, and closed with an accurate account. That is the failure this review
exists to catch, and it has already been caught once here.

The generalisable tell: **the exec record and the plan row disagreeing is a
stronger signal than either alone.** A sweep that reads only the plan cannot see
it, and this campaign's own history is the proof that it happens.

## Finding 4 -- the evidence trail has two structural gaps, both recorded

34 of 306 steps carry no execution record, and 18 phases across 10 waves carry no
phase summary at all. Both are documented in the sibling audit with the reason
retrospective authoring is refused: a record written now would imply a
contemporaneous account nobody has, and no later reader could tell it from a real
one.

## Finding 5 -- the deferred set is named, not implied

The campaign's carry-forwards are recorded rather than left to be discovered: the
call-shape measurement above; a citation-table gap and an outbound B2B/B2C fork,
**both since closed** under `iva-service-localisation` and
`iva-art-69-dos-services`; sibling advisories belonging to another feature's live
plan; the Facturae invoice-class vocabulary, **since bundled** with byte-verified
provenance; and a docs search artefact whose door is deliberately unlocked and
explicitly needs a ruling before first use.

That three of the six have been closed since the campaign ended is the evidence
that naming a carry-forward precisely is what makes it actionable later.

## Verdict

**Structurally complete, with one substantive carry-forward and two
bibliographic gaps, all three stated rather than absorbed.**

The campaign may be declared closed. The one item that would block a stricter
reading -- the ADR's own measurable question -- is formally deferred here with
its blocker named, which is what the close rule requires of an item that cannot
be verified: closed with verification, or deferred with a reference. This is the
reference.
