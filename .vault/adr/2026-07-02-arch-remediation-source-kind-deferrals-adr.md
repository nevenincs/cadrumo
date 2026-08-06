---
tags:
  - '#adr'
  - '#arch-remediation-source-kind-deferrals'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:7993cb1c450d985c11958bb836236e687f018be4f50916d175552f41aeb922be'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-07-01-iva-complexity-hardening-scope-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
  - '[[2026-07-06-arch-remediation-source-kind-deferrals-research]]'
---
# `arch-remediation-source-kind-deferrals` adr: `deferred source-kind re-ratification with promotion targets` | (**status:** `accepted`)

## Problem Statement

The audit's register item D4 requires each member of
`DEFERRED_SOURCE_KINDS` to either gain a live resolver or have its deferral
re-ratified by an ADR with a target condition; D5 requires the RESERVED
tier to stay explicitly tracked. The six deferred kinds fall into two
groups with different maturity: two IVA kinds whose promotion mechanics are
already designed in accepted ADRs (prorrata regularizacion;
bienes-inversion regularizacion), and four informativa detail-row kinds
(M184 atribucion members, M232 related-party operations, M720 foreign
assets, M360 refund operations) deferred by the aggregation-taxonomy ADR
pending per-kind grounded design. This ADR is the re-ratification: it names
each kind's promotion target so the deferral set is governed, not merely
enumerated.

## Considerations

- The aggregation-taxonomy ADR's safety floor is non-negotiable and already
  live: every deferred kind surfaces a standing operator advisory; none may
  ever enter the manual-input allowlist (that would re-silence it).
- The two IVA kinds carry accepted, recent design: prorrata promotes to a
  live mesh binding on the `iva_compensation_annual_partition` precedent
  once the provisional-carry mechanism is proven end to end;
  bienes-inversion promotes once the prorrata-definitiva source lands (it
  consumes the same definitive percentage). Their targets are dependencies,
  not dates.
- The four informativa kinds have no resolver design and no current filing
  pressure: each is a Sheets-pull-only detail-row surface whose promotion
  needs its own grounded ADR (per-kind row taxonomy, evidence shape,
  detail-record fold semantics).
- Wave 1 froze NEW source kinds and resolver conventions until the bindings
  campaigns close; this ADR governs the EXISTING deferred set and does not
  touch the freeze.

## Considered options

- **Option A: promote everything now.** Rejected: the four informativa
  kinds have no grounded design; forcing resolvers would invent legal
  behavior (safety-gates violation) or ship hollow shells (source-hygiene
  violation).
- **Option B: leave the set as code comments.** Rejected by the program's
  deferral-as-data mandate - comments are how the inversion deferrals
  rotted.
- **Option C (chosen): re-ratify per kind with typed target conditions**
  recorded on the declaration itself, reviewed at program Wave 4 closure
  and at every swarm-audit pass.

## Constraints

- Dispositions ratified by this ADR: `prorrata_regularizacion` - promote
  when the provisional-carry store plus Q4 regularisation is proven end to
  end (its owning ADR's stated trigger); `bienes_inversion_regularizacion`
  - promote when the prorrata-definitiva source lands (dependency on the
  former); `atribucion_member`, `related_party_operation`, `foreign_asset`,
  `refund_operation` - deferral re-ratified with NO promotion date; each
  promotion requires its own grounded design ADR, and the review trigger is
  that modelo's next hardening campaign or an operator filing need,
  whichever comes first.
- The RESERVED tier (counterpart/invoice headroom) stays: a reserved kind
  cannot be consumed without promotion, enforced by the existing
  enrollment-status gate.
- The advisory surface is invariant: any change that would remove or mute
  a deferred kind's calculate-path advisory is a violation of
  no-silent-under-declaration, not a cleanup.
- Promotion of any kind must enroll under the mesh ownership contract
  (exclusive claim, novel-source gate) - no side-path resolvers.

## Implementation

The declaration in the source mesh gains, per deferred member, a structured
target annotation (owning ADR stem plus trigger condition) replacing the
current free-prose comments - the same declaration the enrollment-status
gate already reads, extended so the gate can assert that every DEFERRED
member carries an owning ADR and a trigger. The two IVA kinds' annotations
cite their accepted ADRs; the four informativa kinds cite this ADR. Wave 4
closure and the swarm-audit cadence re-read the annotations: a kind whose
trigger has fired but which remains deferred is a finding, mechanically
detectable.

## Rationale

This is the smallest decision that makes D4 true: nothing is promoted
prematurely (the four informativa kinds genuinely lack design; the two IVA
kinds genuinely wait on a store that is mid-build), yet no deferral remains
ungoverned - each carries an owner, a trigger, and a gate that notices a
fired trigger. It generalises the deferral-as-data pattern the audit
praised into the one place it was still half-prose.

## Consequences

- The deferred set becomes self-auditing; "we forgot to promote it" is now
  a test failure at the swarm cadence, not an archaeology exercise.
- The four informativa kinds are explicitly allowed to stay deferred
  indefinitely - honest, and bounded by the per-modelo review trigger.
- A small schema change to the deferral declaration and gate; no
  calculate-path behavior change whatsoever.
- Future source kinds inherit the pattern at birth: a new deferred kind
  without an owner plus trigger fails the gate.
