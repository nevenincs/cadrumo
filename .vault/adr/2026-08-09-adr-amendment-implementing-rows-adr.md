---
tags:
  - '#adr'
  - '#adr-amendment-implementing-rows'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:14871eadd7beff35592a357ee900e810efa8fe637d557f709c88e55e332177d0'
related:
  - "[[2026-08-09-adr-amendment-implementing-rows-roll-up-authorization-research]]"
  - "[[2026-06-09-modelo-iva-routing-carry-adr]]"
  - "[[2026-08-07-rate-box-evidence-assertion-adr]]"
  - "[[2026-08-07-recargo-equivalencia-source-of-truth-adr]]"
---

# `adr-amendment-implementing-rows` adr: `one roll-up authorization for the existing cross-domain plan` | (**status:** `accepted`)

## Problem Statement

The existing plan coordinates implementing rows governed by three accepted source ADRs, but its feature tag has no same-feature ADR. VaultSpec Core consequently refuses to scaffold its execution records even when the plan is selected explicitly. This record decides whether to authorize the existing bundle, split it, or move its execution records under other feature identities. See `2026-08-09-adr-amendment-implementing-rows-roll-up-authorization-research`.

## Considerations

- The three source ADRs remain the governing contracts for their respective rows; this record must not fork their domain facts.
- The existing plan already owns dependency order, parallelization, scope, and combined completion.
- `vaultspec-core@0.1.56` requires an ADR carrying the execution feature tag before related-plan selection can complete.
- Feature identity must remain aligned across the plan and its execution records.
- Plan splitting is warranted by delivery boundaries, not scaffolding mechanics.

## Considered options

**Keep the existing plan and add a same-feature coordination ADR.** Chosen. It supplies the missing lifecycle authorization while retaining one execution boundary and the three source ADRs as the substantive authorities.

**Split the plan into source-feature plans.** Rejected. It adds coordination surfaces without changing ownership, dependencies, release boundaries, or implementation contracts.

**Create cross-feature execution records and select this plan with `--related`.** Rejected. It mis-tags the work, separates execution identity from plan identity, and treats parent selection as an authorization bypass.

**Leave the plan without executable records.** Rejected. It preserves known implementation debt in a state the owning CLI cannot execute or close honestly.

## Constraints

The parent source ADRs are accepted and stable enough to authorize their existing rows. This record does not amend, supersede, reinterpret, or consolidate them.

The roll-up ADR authorizes only coordination and bundling. Domain-contract changes remain in the corresponding source ADR.

The plan and every execution record retain the `adr-amendment-implementing-rows` feature tag. `--related` names the parent plan; it does not permit another feature tag to stand in for authorization.

No plan split may be introduced solely to satisfy document scaffolding.

## Implementation

Retain `2026-08-07-adr-amendment-implementing-rows-plan` as the single execution plan. Add this ADR to that plan's authorizing related set while preserving the three source ADR links. Create each remaining execution record with the plan's feature tag and the existing plan as its related parent.

For every Step, the corresponding source ADR remains the governing contract. This roll-up record supplies no substitute domain requirements and adds no implementation behavior.

## Rationale

The chosen option is the only one that satisfies the lifecycle gate without falsifying ownership or inventing a delivery boundary. The research shows that explicit parent selection and same-feature authorization are separate checks in `vaultspec-core@0.1.56`; a roll-up ADR supplies the missing authorization, whereas mis-tagging attempts to evade it.

The existing plan already expresses the shared dependency and completion structure. Splitting it would optimize documentation for scaffolding rather than implementation.

## Consequences

Execution records can be scaffolded under their truthful feature identity. The three source ADRs remain independently authoritative, and the plan retains one combined completion boundary. Future changes must distinguish coordination changes, which may amend this record, from domain-contract changes, which belong in the relevant source ADR.
