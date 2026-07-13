---
tags:
  - '#adr'
  - '#binding-adr-corpus-reconciliation'
date: '2026-07-05'
modified: '2026-07-10'
related:
  - "[[2026-06-26-bindings-architecture-unification-research]]"
  - "[[2026-06-26-binding-adr-corpus-reconciliation-plan]]"
---

# `binding-adr-corpus-reconciliation` adr: `no-apex binding ADR corpus reconciliation authority` | (**status:** `accepted`)

## Problem Statement

The `binding-adr-corpus-reconciliation` plan is a vault-only reconciliation
campaign: it re-points or supersedes older binding and sourcing ADR status blocks so
semantic search converges on the phase and foundational decisions instead of on the
rejected central apex ADR.

The work was already checked in the plan and landed in a sequence of ADR edits, but
the feature had no same-feature ADR. That left the plan graph malformed and blocked
the vault CLI from scaffolding execution records for the checked steps. This ADR
exists to record the feature's authority without reopening the rejected apex.

## Considerations

- The grounding research found real ADR-corpus conflicts across source-kind
  vocabulary, resolver-contract ownership, relation versus `previous_filing`
  fold-in, compensacion carry, enrollment-state tracking, and binding vocabulary.
- The operator explicitly rejected a central apex as the governing home. The plan
  therefore reconciles individual ADRs around the phase ADRs and stable
  foundational ADRs.
- The existing plan is already the approved execution ledger for the per-ADR edits;
  this ADR must anchor that ledger, not replace it with a new campaign.
- No source code, registry data, rules, or runtime behaviour is changed by this
  decision.

## Considered options

- **Create a new governing apex ADR.** Rejected. That is the approach the operator
  declined, and reviving it would contradict the demoted apex status block.
- **Leave the feature plan without a same-feature ADR.** Rejected. The vault
  lifecycle requires an ADR before exec records; leaving the gap would preserve
  checked steps with no executable evidence ledger.
- **Chosen: create a narrow curation ADR.** This records the no-apex authority for
  the already-approved corpus reconciliation and gives vault a same-feature decision
  node, while making the phase and foundational ADRs remain the canonical technical
  direction.

## Constraints

- This ADR cannot supersede or amend the phase ADRs. It is only the authority record
  for the corpus-reconciliation plan.
- The rejected `bindings-architecture-unification` apex remains rejected; its C1-C6
  analysis remains historical input, not canonical architecture.
- Future phase 2.2, 2.3, and 2.4 implementation decisions must land under their own
  feature ADRs or existing accepted phase ADRs, not under this curation record.
- Execution evidence for the 12 checked plan steps must be recorded as step records
  against the existing plan.

## Implementation

The feature authority is:

- Research: the existing bindings architecture unification research provides the
  conflict inventory and recommendation set.
- Decision: this ADR records the no-apex curation decision and explicitly rejects a
  new governing apex.
- Plan: the existing binding ADR corpus reconciliation plan remains the execution
  ledger for the 12 per-ADR status edits and retargeting steps.
- Exec: each checked plan step gets a reconstructed execution record citing the
  landed commit or commit set that performed the ADR edit.

## Rationale

The defect is not missing runtime architecture; it is missing vault authority for a
completed documentation-corpus reconciliation campaign. The research and plan already
identify the architecture: phase ADRs and foundational ADRs are canonical, while the
central apex is rejected. A narrow curation ADR is the least-powerful record that
unblocks honest exec-record reconciliation without changing that architecture.

This also matches the plan's own statement that supersession targets phase or
foundational ADRs, never a central apex document.

## Consequences

The feature graph now has a same-feature ADR, so the vault CLI can scaffold missing
exec records for checked steps. Future readers can distinguish the rejected apex from
the accepted no-apex reconciliation campaign.

The remaining risk is historical: several plan steps landed before their exec records
were created. The follow-up action is therefore reconstruction, not implementation.
Each reconstructed step record must name the evidence commit and state whether it was
a single-ADR edit or the broader cross-campaign retargeting pass.
