---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8b994cb669c8ea84f342e8db1ced900a8d43d7bbc32fa48f3552a9771465130e'
related:
  - "[[2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-lifecycle-grounding-research]]"
  - '[[2026-08-22-source-casilla-integration-adr]]'
---
# `source-casilla-integration` adr: `modelo 840 source and repeated row owner deferral` | (**status:** `accepted`)

## Problem Statement

The accepted source-connectivity framework requires a model-scoped owner decision
before a source kind, resolver, row binding, producer, layout, or census claim
is introduced.  `2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-lifecycle-grounding-research`
grounds two genuine M840 fact families but no non-lossy source owner for either.
This ADR decides the bounded refusal without changing the registry or generic
transport contract.

## Considerations

- `2026-08-22-source-casilla-integration-adr` requires a grounded fact,
  compatible destination, durable provenance, secure owner, and encrypted
  replay/review lifecycle before a source connection can be claimed.
- `2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-lifecycle-grounding-research`
  separates the official M840 declaration and local-row fact families from
  layout, observation, and vocabulary-only artefacts.
- `2026-08-24-registry-completeness-closure-modelo-840-record-terminator-and-design-extent-reference`
  assigns generic record-terminator transport to its own export boundary.

## Considered options

### Connect the registry, producer labels, PDF profile, or secure threshold observation now

Rejected.  Those independently useful surfaces do not establish the admitted
M840 source families' non-lossy fact ownership.

### Treat the declaration and local rows as not applicable

Rejected.  The grounded official fact families are genuine; absence of their
source owner is a grounding gap rather than inapplicability.

### Hold the two exact source families at a model-scoped grounding boundary

Accepted.  Preserve every existing narrow contract while refusing to promote it
into a wider M840 lifecycle claim.

## Constraints

- The decision applies only to Modelo 840 revision `2003-y-siguientes` and
  period `0A`; it does not choose another temporal window or promote a filing
  authority.
- Generic CRLF transport, an official byte coordinate, a producer vocabulary
  key, a record-layout artefact, and a post-filing observation cannot satisfy a
  source-owner predicate.
- The existing secure annual IAE threshold observation, informational targets,
  and generic transport remain distinct contracts.  This ADR neither removes
  them nor declares a direct/manual M840 source lifecycle.
- No source taxonomy, census, binding, casilla, producer, extractor, renderer,
  export, or runtime change is authorized by this decision.

## Implementation

`source-connectivity-campaign` owns two Modelo 840 `grounding_blocked` source
families: the declaration/activity family and the individual `RelaciÃ³n de
locales` row family.  The owner must keep them separate; a partial declaration
fact cannot stand in for a local row, and a local-row value cannot stand in for
the whole declaration.

No census candidate or disposition row is created by this ADR because no
candidate has the framework's fact/grain/destination/owner evidence.  No M840
binding, resolver, fixture, source-owned export, or writer follows from this
refusal.  The generic CRLF transport remains governed independently and does
not become an M840 value lifecycle.

### Reopening predicate

A later, explicitly authorized M840 slice may reopen one family only when it
proves all of the following for that family:

1. An authoritative, encrypted Cadrumo carrier and acquisition route with a
   durable declaration or per-local identity; the local route must retain every
   required address/municipality coordinate and the distinct `Total`,
   `Rectificada`, and `Computable` values.
2. Exact native grain, period/event applicability, zero, absent-row,
   inapplicable, correction, override, and collision semantics; a bounded
   partial owner must be classified as such rather than silently widening to
   the other family.
3. A law-selected registry semantic map and row/binding destinations that
   exclude AEAT-reserved transport fields and preserve repeated-row identity.
4. Resolver ownership, acquisition provenance and fingerprint, encrypted
   persistence/reload, deterministic replay, diagnostic/refusal behavior, and
   an operator review route for the same source-to-target identity.
5. Independently grounded, supported export evidence where export is proposed;
   generic CRLF transport must be proven separately after, not instead of, the
   preceding source proof.

## Rationale

The accepted option is the only one compatible with
`2026-08-22-source-casilla-integration-adr`: it keeps genuine required facts
visible while denying every shortcut that would infer acquisition or ownership
from presentation, observation, or transport.  It gives the campaign a
falsifiable, family-specific reopening boundary without blocking the existing
narrow contracts.

## Consequences

- S231 closes with an evidence-backed model-scoped `grounding_blocked` refusal,
  not a source connection, a manual-by-design conclusion, or a filing claim.
- Future M840 work must establish a source owner before it can add a candidate,
  binding, resolver, lifecycle fixture, or source-owned repeated-record export.
- Existing generic transport and narrow observation surfaces remain available
  under their own decisions, but cannot be cited as proof that the deferred M840
  facts are connected.
