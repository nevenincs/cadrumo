---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:3248f2553accc1920644a7ef9f33fcf833dd52631837be6433affa9aa675e213'
related:
  - "[[2026-08-25-source-casilla-integration-modelo-220-group-value-source-grounding-research]]"
---

# `source-casilla-integration` adr: `m220 source owner deferral` | (**status:** `accepted`)

## Problem Statement

Choose whether M220 group-value evidence authorizes a source connection now,
or must remain a bounded source-owner deferral.

## Considerations

- The M220 grounding research establishes separate 2024/2025 designs and a
  composite group/member grain.
- The accepted connectivity ADR requires source ownership and a complete
  lifecycle before a connection is admitted.

## Considered options

- Treat layouts, direct input, Modelo 200, or M222 as a source route: rejected;
  it would substitute a target or adjacent relationship for ownership.
- Mark the candidate not applicable: rejected; the evidence describes a real
  M220 fact domain.
- Defer as ingress-blocked: accepted.

## Constraints

No existing secure owner can preserve the required composite source fact and
its complete lifecycle. The accepted connectivity framework is stable and
continues to be the sole route for any later connection.

## Implementation

Classify M220 group values as `ingress_blocked`, owned by
`source-connectivity-campaign`. Add no producer, binding, resolver, casilla
linkage, layout, export route, or census row in this decision.

Reopen only when one encrypted, non-lossy owner retains composite group and
representative/dominant identity; each member identity and its individual
declaration/source reference; exact tax period and M220 revision; native
member/group value role, unit, and value identity; capture provenance and
fingerprint; and distinct absent/inapplicable/zero semantics. It must also
prove resolver enrollment, diagnostics/provenance, encrypted persistence and
replay, operator/review reachability, and source-owned supported export for
each 2024 and 2025 era.

## Rationale

Deferral is the only option consistent with the absence of ownership/lifecycle
evidence in `2026-08-25-source-casilla-integration-modelo-220-group-value-source-grounding-research` and the framework decision in
`2026-08-22-source-casilla-integration-adr`.

## Consequences

M220 remains unconnected without a false source claim. A later accepted owner
may reopen this disposition only by meeting every stated limb; direct/manual
M220, Modelo 200, M222, and export coordinates remain insufficient substitutes.
