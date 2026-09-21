---
tags:
  - '#adr'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:48be7296cca94c574488e21df89461596b710cd7071e20d2545ee20af1b149ad'
related:
  - "[[2026-09-21-iva-workflow-m303-filing-evidence-authoring-reference]]"
  - "[[2026-09-21-iva-workflow-adr]]"
---
# `iva-workflow` adr: `M303 filing evidence production authoring boundary` | (**status:** `accepted`)

## Problem Statement

Installed Modelo 303 calculation consumes a fully formed filing-instance
evidence envelope, but production has no owner that creates it. Treating the
current plaintext JSON input as authoritative would allow callers to assert
authority-owned and derived facts and would not ground several operator facts in
secure evidence. The ownership gap is measured in
`2026-09-21-iva-workflow-m303-filing-evidence-authoring-reference`.

## Considerations

- The calculation revision is already the encrypted durable owner of the
  validated envelope; another aggregate or draft store is unnecessary.
- Authority, profile and calculation owners already derive part of the
  envelope, while genuine elections and facts still require operator input.
- Nominal evidence references and insolvency without any reference cannot
  establish filing-grade provenance.
- Sensitive financial or taxpayer input must not become a default plaintext
  artifact or appear in diagnostics.

## Considered options

1. Keep the complete external JSON envelope as production truth. Rejected
   because it permits caller ownership of derived facts and unresolved evidence.
2. Add a separate persisted filing-evidence draft aggregate. Rejected because it
   creates another store and lifecycle beside calculation revisions.
3. Add a shared transient application authoring operation that accepts only
   genuine operator assertions and secure references, derives the remaining
   fields through existing owners, and hands the typed result directly to
   calculation. Chosen.

## Constraints

- Authority snapshot, Orden, record design and DANA availability come only from
  the canonical bundled authority.
- Profile scope comes only from the selected secure profile. Calculated results
  and endpoint observations come only from existing application calculation.
- A supplied evidence reference must resolve to an authorized secure record of
  the expected role, taxpayer/profile scope and relevant period. Missing, stale,
  cross-scope, duplicate-conflicting or contradictory evidence refuses.
- No latest-wins precedence, inferred zero, frontend tax arithmetic, test
  fixture import or operator override of derived facts is permitted.
- Optional regimes refuse when their complete evidence contract is not
  available. Refusal of an optional regime must not disable an otherwise
  grounded ordinary Modelo 303 filing.

## Implementation

Extend the existing Modelo calculation application orchestration with a
transient filing-input authoring request. It carries filing identity and period,
typed operator elections or assertions, role-labelled secure references and
expected identities needed to detect stale composition. The operation resolves
references through existing secure owners, obtains authority and profile facts
from their canonical resolvers, derives calculation-owned values, constructs and
validates `FilingInstanceEvidence`, and passes it directly into the existing
calculation-revision persistence flow.

The installed CLI exposes this shared operation through one sensitive input
channel. Standard input is canonical; an explicit file is only a warned
convenience. The CLI never accepts authority-owned or derivable envelope fields,
does not echo the request and returns only sanitized revision identity and
diagnostics. The request is not persisted separately. The validated envelope is
durable only inside the encrypted calculation revision.

The first slice supports the ordinary 2025 Modelo 303 path. Insolvency gains a
mandatory secure evidence identity before it can be enabled. Exemption and
simplified-regime branches are enabled separately only after every assertion and
reference in that branch has an existing secure owner and a complete refusal
contract.

## Rationale

The transient application operation preserves one durable owner while preventing
the CLI from becoming a tax-fact calculator or evidence authority. It reuses the
existing authority, profile, calculation and encrypted persistence boundaries,
closes silent caller precedence, and permits the ordinary installed journey to
advance independently of optional-regime evidence work.

## Consequences

Production no longer depends on a hand-authored complete evidence envelope for
ordinary Modelo 303 calculation. Recalculation creates the normal immutable
calculation revision and preserves earlier evidence through the existing
lifecycle. Optional regimes may remain truthfully unavailable longer, and secure
reference resolution adds explicit failure states, but incomplete or
contradictory evidence can no longer look filing-ready. Existing full-envelope
JSON remains a compatibility-free internal/testing input until removed; it is
not an accepted production authoring source.
