---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-11-04'
body_schema: 'body-v1'
body_hash: 'sha256:653592a72d6aa07db756405a153ebc17bf63be2c6a8ce9965cb462ba6bc9dca9'
related:
  - "[[2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research]]"
  - '[[2026-08-22-source-casilla-integration-adr]]'
---

# `source-casilla-integration` adr: `m390 2021 source owner deferral` | (**status:** `accepted`)

## Problem Statement

The accepted source-connectivity framework requires a model-scoped source-owner
decision before a source domain, binding, producer, or layout is authored. The
exact Modelo 390 annual surface of the scoped filing year (the year named in this
record's title) is grounded in
`2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research`,
but no complete pre-filing value owner is. This ADR decides the bounded
scoped-year outcome without changing the parser or importing later M390 behavior.

## Considerations

- `2026-08-22-source-casilla-integration-adr` governs the disposition
  vocabulary and requires a non-lossy, encrypted, provenance-carrying lifecycle
  before a source claim can be connected.
- `2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research`
  distinguishes the official scoped-year annual record from the ten parser
  observations, read-only filed evidence, and later M390 implementation.
- `2026-06-02-m390-annual-autoconsumo-promotor-source-adr` and
  `2026-06-21-m390-iva-carry-boxes-adr` retain their narrow, later M390
  aggregation decisions; neither supplies complete scoped-year source ownership.

## Considered options

### Connect the parser, filed declaration, or later routes now

Rejected. Each is either a post-filing observation or a partial/later route; none
is the non-lossy scoped-year fact owner the framework requires.

### Treat the complete annual surface as not applicable

Rejected. The official scoped-year annual record is genuine and required; absence of a
source owner is a grounding gap, not an inapplicability determination.

### Hold the exact annual surface at a model-scoped grounding boundary

Accepted. Preserve genuine parser observations, filed-declaration read evidence,
and independent later-model routes, while refusing to claim they are a complete
scoped-year source connection.

## Constraints

- The decision applies only to Modelo 390, the scoped filing year, period `0A`; it
  neither extends to another M390 revision nor changes any legal temporal
  selector.
- Parser coordinates, export fields, static-layout evidence, and post-filing
  observations remain inadmissible as proof of a pre-filing value owner.
- Existing encrypted filed-declaration custody is read-only historical evidence;
  it neither supplies absent facts nor substitutes for the calculation-revision
  source lifecycle.
- No runtime, source taxonomy, binding, producer, registry, census, or layout
  change is authorized by this decision.

## Implementation

The complete Modelo 390 scoped-year annual casilla/value-arrival surface is
`grounding_blocked`, owned by `source-connectivity-campaign`. This is a
model-scoped refusal to connect, not a claim that
the form, its fields, the parser, a manual path, or a later filing route is
inapplicable. No census row is created by this decision; a later owner may add
one only with the bounded follow-up and review fields required by the framework.

The ten scoped-year informational parser casillas remain observation-only. A secure
filed-declaration observation remains usable only as read evidence under its
own contract. Existing M390 routes remain exact to their declared revision and
target. None is a resolver, producer, or export authority for the unconnected
scoped-year annual surface.

### Reopening predicate

Reopen this boundary only for one bounded scoped-year vertical slice that demonstrates
all of the following:

1. A field-complete scoped-year semantic map for the required annual declaration scope,
   including taxpayer/group and representative facts, repeated activity and
   prorrata rows, sector/territory/regime grain, sign, units, rounding, and the
   distinct zero, inapplicable, absent, and supplied-value semantics.
2. Officially grounded source facts and authoritative encrypted carriers for
   every admitted value family, with annual aggregation, durable provenance,
   collision/override policy, and an explicit manual-by-design result wherever
   automation is not justified. Quarterly Modelo 303 or later M390 routes may
   be used only after this proof selects their exact scoped-year facts and boundaries.
3. A law-selected registry revision exact to the scoped year, promoted only as evidence
   permits, with the necessary casillas, bindings/formulas/relations, resolver
   ownership, and non-casilla producer ownership.
4. An operator-reachable encrypted calculation-revision lifecycle that persists,
   reloads, replays, and reviews the same source-to-target identity and its
   provenance.
5. Separately grounded scoped-year filing-layout and serializer evidence with complete
   emitted-byte proof. Coordinates may validate the serialization only after the
   preceding source proof; they cannot satisfy it.

## Rationale

`2026-08-25-source-casilla-integration-m390-2021-annual-value-arrival-grounding-research`
eliminates the only shortcuts that could make an immediate connection look
plausible. The accepted option preserves useful parser and historical evidence
without turning an observation into a source fact or silently narrowing the
official annual record. It is the only option consistent with the framework's
losslessness and provenance requirements.

## Consequences

- S228 closes as a grounded model-specific refusal, with no source-connectivity
  or filing capability claim added.
- Future work has a falsifiable reopening predicate and cannot back-project a
  later M390 route or a PDF coordinate into scoped-year ownership.
- The scoped-year parser and read-only filed-declaration evidence remain available for
  their existing observation and reconciliation purposes.
- A future implementation must be an explicitly authorized, full lifecycle
  slice; a layout-only or parser-only change does not close this boundary.
