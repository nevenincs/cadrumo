---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fe489b6382037f71d66104ab1000f01a27898a007e95bd2913edde04155023e9'
related:
  - "[[2026-08-25-source-casilla-integration-modelo-721-structured-message-source-grounding-research]]"
  - '[[2026-08-22-source-casilla-integration-adr]]'
---

# `source-casilla-integration` adr: `m721 structured-message source owner deferral` | (**status:** `accepted`)

<!-- DOCUMENT BOUNDARY:
     This record owns the decision and only the decision. Grounding evidence
     lives in the related research/reference documents and is cited by stem
     (e.g. `2026-02-04-editor-demo-research`), never restated - a restated
     fact forks and goes stale. A fact this record needs but the grounding
     lacks is added to the grounding first, then cited. -->

## Problem Statement

Decide whether the exact Modelo 721 source facts for its selected 2023 and
2024 structured-message eras authorize a connection, a non-applicable result,
or a bounded source-owner deferral. The factual record is
`2026-08-25-source-casilla-integration-modelo-721-structured-message-source-grounding-research`.

## Considerations

- `2026-08-22-source-casilla-integration-adr` requires a non-lossy encrypted,
  provenance-carrying lifecycle before a source domain can be connected.
- `2026-08-25-source-casilla-integration-modelo-721-structured-message-source-grounding-research`
  distinguishes two finite official target grammars from the manual and
  encrypted-observation routes that currently exist.
- `2026-06-02-modelo-721-cripto-data-fidelity-adr` remains the narrow home for
  M721 threshold-continuity over manually entered observations; it does not
  decide complete source ownership.

## Considered options

### Connect the BOE annex, SOAP/XML contract, manual casillas, or encrypted observations

Rejected. Each is respectively a declaration target, transport contract,
direct-input surface, or retained manually supplied observation; none is the
complete source owner required by the connectivity framework.

### Treat the two message fact domains as not applicable

Rejected. The researched official eras establish genuine repeated custody and
valuation facts. Missing secure ingress is an ownership gap, not proof that the
facts do not apply.

### Defer both selected annual fact domains at an ingress boundary

Accepted. Retain direct manual entry and its secure observation history while
refusing a source connection until an accountable owner can preserve the
complete source fact and its lifecycle for each exact era.

## Constraints

- This decision is limited to Modelo 721, annual period `0A`, and the selected
  2023 and 2024 revisions. It does not select, classify, or imply continuity
  for 2025 or later.
- XML/SOAP/WSDL/XSD, official field grammar, transport validation, export
  coordinates, and emitted bytes remain target or serializer evidence only;
  none is source acquisition or provenance evidence.
- The accepted direct/manual casillas and encrypted observation history remain
  available at their current scope. They neither become a source binding nor
  provide a second evidence channel for the M721 advisory.
- This ADR authorizes no source kind, source catalogue entry, census row,
  binding, resolver, producer, registry/casilla, lifecycle, layout, serializer,
  or export change.

## Implementation

Classify the unconnected M721 custody-and-valuation source domain for
`2023/0A` and `2024/0A` as `ingress_blocked`, owned by
`source-connectivity-campaign`. This is a model-scoped refusal to connect,
not a statement that its BOE messages, manual fields, encrypted observations,
or filing work are absent or invalid. No census row is created by this decision.

### Reopening predicate

Reopen only through a separately approved, exact-era vertical slice that proves
all of these conditions for the requested era; one era cannot stand in for the
other:

1. A complete semantic map for the official message fact: declarant and annual
   revision, detail identity, ownership role, custodian identity and location,
   currency identity, units, EUR valuation and its origin, balance,
   status/date branch, precision, and each field's required or repeated grain.
2. One encrypted, non-lossy source owner that acquires the admitted custodian
   and valuation facts with a durable external source identity and fingerprint,
   capture provenance, temporal scope, and collision/override policy. It must
   preserve distinct supplied, zero, absent, inapplicable, and end-of-condition
   semantics without interpreting an omitted manual row as one of them.
3. An explicitly bounded manual-by-design result for any official field that
   no authoritative source legitimately supplies; direct entry may remain only
   under that reviewed boundary and cannot fill a connected source claim.
4. Registry source selection, typed resolver and non-casilla ownership, then
   encrypted calculation-revision persistence, replay, diagnostics/provenance,
   and operator/review reachability for the same source-to-target identity.
5. Independently, the S97--S99 route must hold an exact hash-pinned technical
   contract inventory and prove the canonical locally generated output for the
   same law-selected era. This validates a later serializer only; it cannot
   substitute for the preceding source proof.

## Rationale

The accepted deferral is the only option that preserves the real manual and
historical routes without turning any declaration target or retained result into
the source fact it should evidence. It follows the losslessness and provenance
requirements of `2026-08-22-source-casilla-integration-adr` and the two-era
factual separation in
`2026-08-25-source-casilla-integration-modelo-721-structured-message-source-grounding-research`.

## Consequences

- Modelo 721 remains unconnected for its 2023 and 2024 source domains, with no
  inferred binding, producer, resolver, or export authority.
- The genuine direct/manual casillas and encrypted threshold-continuity
  observations remain distinct, usable paths; they are not silently withdrawn
  or promoted.
- A future implementation has an era-specific, falsifiable proof contract and
  cannot use a WSDL, layout, export, or post-entry observation as a shortcut to
  source ownership.
