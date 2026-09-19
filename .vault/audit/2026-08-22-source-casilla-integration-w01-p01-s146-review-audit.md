---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:fe9f62ede216133c6000b2ae1045f02d55d06010d74996ebca51ee7aa8deb448'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `source-casilla-integration` audit: `W01.P01.S146 Calculation Route Identity Remediation Review`

## Scope

Reviewed remediation commit `51f298a833` against the blocking S140 review in
`56f9570a40`, the accepted connectivity ADR, the S146 execution record, and the
production calculation route. The review independently reprobed renamed
resolver ids, owned-source drift, resolver-free non-manual rows, invented and
duplicate manual pseudo-owners, a typed manual owner, an unknown resolver
class, and every non-canonical stage assignment for every typed production
resolver.

Verification comprised 91 direct adversarial mutations, 37 focused
calculation-route and source-disposition tests, 73 broader live enrollment,
source-mesh, borrador, and IVA-wallet tests, Ruff over both changed Python
paths, and static tracing of each runtime route consumer. All 201 checks passed.

## Findings

### identity-mutation-refusal | low | Every requested declaration identity mutation now fails closed

The validator rejects a renamed resolver id, altered owned-source tuple,
`resolver_type=None` on a non-manual row, invented or repeated manual owners,
and a manual row carrying a resolver class. A synthetic resolver class that is
absent from the canonical type-to-stage specification is also refused before
it can participate in source disposition. Independent probes observed the
specific failure at each boundary rather than relying only on the shipped
test expectations.

### stage-authority-independence | low | Canonical stage identity is not inferred from supplied ownership rows

`_CANONICAL_RESOLVER_STAGES` is a separate immutable tuple of resolver classes
and their production stages. The public ownership rows are derived from that
specification, while validation reconstructs a class-to-stage authority from
the specification and compares each supplied row against it. Consequently,
mutating the public tuple's rows cannot mutate the validating authority. All
84 wrong-stage probes—four alternative stages for each of 21 typed
resolvers—were rejected. The shipped parametrized test independently moves
every typed resolver away from its canonical stage.

### runtime-route-consumption | low | Production composition continues to consume the validated route

Pre-mesh profile, borrador, and IVA-wallet paths call
`require_calculation_route_resolver`; ordinary mesh and conditional resolution
use the same guard in calculation composition; and post-mesh prorrata plus
bienes de inversión use it during source staging. Source policy and handled
source projections continue to derive from the public route. The 73 live-path
tests passed, so the stricter declaration gate did not detach or bypass runtime
composition.

### release-gate | low | The S140 blocker is resolved and S145 may proceed

No critical, high, or medium finding remains from this review. The remediation
satisfies every failure mode required by the S140 audit while retaining the
independent reflective and runtime-consumption boundaries. S145 is unblocked
for resolver-identity provenance work.

## Recommendations

Proceed with S145. Preserve `_CANONICAL_RESOLVER_STAGES` as the independent
type-and-stage authority, retain the full adversarial mutation suite, and make
future resolver enrollment update this authority and the runtime route in the
same bounded step.
