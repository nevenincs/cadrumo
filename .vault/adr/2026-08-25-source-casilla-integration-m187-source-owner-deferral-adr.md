---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:52c66b6d595ee957fd4333d187d74b7624c7d052682138955d729e553709826c'
related:
  - "[[2026-08-25-source-casilla-integration-m187-payer-entity-iic-grounding-research]]"
---
# `source-casilla-integration` adr: `m187 source owner deferral` | (**status:** `accepted`)

## Problem Statement

Choose whether existing M187 payer/direct paths can own the distinct Article 42 entity/IIC population.

## Considerations

The related M187 grounding research establishes distinct filer populations and no non-lossy secure source owner.

## Considered options

- Enroll an existing payer/direct path: rejected; it collapses distinct authority.
- Defer ownership: accepted.

## Constraints

No owner, durable identity/provenance carrier, or replayable M187 resolver is evidenced.

## Implementation

Retain current manual/direct surfaces; add no binding, resolver, export route, or census promotion until a separately accepted carrier exists.

## Rationale

Deferral preserves the non-substitutability established by `2026-08-25-source-casilla-integration-m187-payer-entity-iic-grounding-research`.

## Consequences

M187 payer/entity/IIC automation remains unavailable; future work must establish ownership before connection.
