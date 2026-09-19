---
tags:
  - '#reference'
  - '#registry-generator'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:9b759c62e836cb2052fc70fe48d0d074e18c54b8b8ed6cb8f799b6cb2fded24c'
related:
  - "[[2026-09-09-registry-generator-adr]]"
  - "[[2026-09-09-registry-generator-plan]]"
---

# `registry-generator` reference: `how the consuming application behaves on an incoherent registry`

## Summary

The consuming side is stronger than the decision record assumed, and that inverts the remedy. The
question deferred was whether the consumer refuses, degrades or proceeds when handed a registry
that is internally inconsistent, temporally incoherent or partially adjudicated. On three of the
four axes the consumer already refuses correctly. The defect is that the producer disarms it.

## The authority refuses an inconsistent revision

Validation accumulates diagnostics and then raises, rather than returning a partially valid
authority. A revision whose declarations contradict each other does not load at all, so no
calculation can read one. This is not theoretical: while this reference was being written the
authority refused to construct because a governed fact referenced a constant that is declared
nowhere, and every consumer of the registry was blocked by that refusal. Fail-closed, demonstrated
in production rather than in a test.

## The wire boundary distinguishes absence from zero

The codec settles absence before projection and never converts it into a quantity. Its own words:
absence is never turned into a semantic value. A field the layout declares required and that has no
value REFUSES rather than rendering, so an omitted mandatory figure cannot reach the wire as a
zero. An optional absent numeric field is filled with zeros, which is what the official record
designs require of a numeric field with no content, and the fill is read from the declaration
rather than chosen by the caller.

So the distinction the decision record worried was missing is present, and it is enforced at the
last boundary before a filing.

## The guard is real and the producer disarms it

The refusal above fires only when the field is declared required. Required-ness is derived by
folding three distinct official facts - the design said optional, the design said nothing, and the
design used a token the matcher does not recognise - into a single false. Roughly twelve thousand
nine hundred fields therefore tell the codec they are optional when the design never said so.

The consequence is precise and it reframes the ruling on undetermined required-ness. That ruling is
not about teaching the consumer a state it lacks. The consumer already refuses an absent mandatory
value. It is about not lying to a guard that already works: every fabricated optional silently
disables the one check that would have caught a missing mandatory figure.

## Temporal coherence is validated, and the corpus was found violating it

A revision states when it applies on three independent axes: its identifier, its date window, and
its period selector. Nothing previously required them to agree, and they were found disagreeing in
both directions. One wealth-tax revision is named "and following" while both its date window and
its year selector are closed; four other modelos carry an open window whose real exclusion is done
by a single-year selector. The validator now refuses the direction a name can lie about - an
identifier claiming open-endedness must be backed by an open window on both axes.

So a temporally incoherent revision is rejected at the authority boundary rather than selected and
used.

## What this changes

The producer-side rigour the decision record rules is worth more than it claimed, not less: the
consumer is already fail-closed, so an honest declaration immediately re-arms real refusals rather
than requiring new consumer machinery. The ruling held pending this lane can proceed on its
existing primitive.

One axis remains genuinely unexamined: whether a calculation can distinguish a value adjudicated
under review from one merely present, as opposed to distinguishing present from absent. The
adjudication mechanism records evidence at the registry boundary, and nothing was found carrying
that distinction forward into a computed result or an explanation. That is the remaining question,
and it is narrower than the one this lane opened with.
