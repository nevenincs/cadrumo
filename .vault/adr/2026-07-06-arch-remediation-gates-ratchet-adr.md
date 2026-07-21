---
tags:
  - '#adr'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-06'
modified: '2026-07-08'
related:
  - "[[2026-07-06-arch-remediation-gates-ratchet-research]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - "[[2026-07-02-arch-remediation-gates-ratchet-plan]]"
---

# `arch-remediation-gates-ratchet` adr: `same-feature authority alignment for Wave 0 ratchets` | (**status:** `accepted`)

## Problem Statement

The architecture-remediation program ADR already accepted the Wave 0
gates-ratchet work: repair the `.importlinter` measurement ledger, replace the
application-to-adapters wildcard with pinned edges, and land ratchet gates so
later waves could be measured against a trustworthy instrument. The
`arch-remediation-gates-ratchet` plan implemented that program decision and is
structurally complete, but the same feature still carried a vault lifecycle
warning because it had a plan without a same-feature ADR.

This ADR closes that authority-alignment warning. It is not a new architecture
decision and does not supersede the program ADR. It gives the completed Wave 0
track a local decision node so feature-scoped vault checks and semantic
discovery do not treat the execution ledger as orphaned.

## Considerations

- The accepted program ADR remains the governing decision for wave ordering,
  ratchet policy, and the Wave 0 instrument repair.
- The related research confirms the current warning is metadata/governance
  only. The Wave 4 ratchet bundle is green, and no code-gate failure remains in
  this feature.
- The gates-ratchet plan's purpose was execution of the already-accepted Wave 0
  mandate, not creation of a standalone runtime architecture.
- Existing warning-closeout ADR precedent uses narrow curation records to give
  feature evidence a same-feature authority anchor without changing behavior.
- A local ADR avoids blurring ownership by adding a second feature tag to the
  parent program ADR.

## Considered options

- **Option A: leave the warning documented only in the program audit.**
  Rejected because the same-feature lifecycle warning would remain and future
  agents would need to rediscover that the program ADR is the parent authority.
- **Option B: tag the program ADR with the gates-ratchet feature.** Rejected
  because that would blur feature ownership and violate the local frontmatter
  shape the feature checks enforce.
- **Option C: create this same-feature curation ADR.** Accepted. It anchors the
  completed gates-ratchet feature locally while preserving the program ADR as
  the governing parent.

## Constraints

- No application code, tests, registry data, import-linter ceiling, lazy-import
  ceiling, data-budget ceiling, or wheel-content policy changes under this ADR.
- Ratchets may still be loosened only by an accepted ADR that explicitly argues
  for the policy change; this curation record is not that mechanism.
- The parent program ADR is stable and accepted. This ADR depends on it and
  narrows only the vault graph-health question for the gates-ratchet feature.
- The completed plan remains the execution ledger. This ADR does not authorize
  a successor plan or reopen any checked step.

## Implementation

Treat the accepted architecture-remediation program ADR as the parent authority
for Wave 0 instruments and this ADR as the feature-local authority pointer for
`arch-remediation-gates-ratchet`. The completed gates-ratchet plan remains the
record of the concrete implementation work: ledger repair, wildcard replacement
with pinned edges, and ratchet-gate enforcement.

No new implementation plan is created from this ADR. If future work changes
ratchet policy, ceilings, import-linter structure, or measurement semantics, it
must use a separate substantive ADR and plan rather than extending this
curation closeout.

## Rationale

The related research found that the feature warning was real but
non-behavioral: a complete feature had no same-feature ADR even though the
parent program ADR already governed the work. Creating a narrow local ADR is
the smallest honest closure. It satisfies the vault lifecycle expectation
without pretending that a new ratchet architecture was chosen after the fact.

## Consequences

- Feature-scoped vault checks can resolve a same-feature ADR for the
  gates-ratchet feature.
- Semantic search now has a direct authority node for Wave 0 ratchet evidence,
  while still pointing readers back to the program ADR for the actual policy.
- This ADR should not be cited as permission to rebaseline ratchets or bypass
  the program's accepted wave-ordering constraints.
- Later substantive ratchet decisions may supersede this curation ADR if they
  replace the policy, not merely because they add more execution evidence.
