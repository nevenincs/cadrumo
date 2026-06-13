---
tags:
  - '#adr'
  - '#renta-cuota-chain-rollout'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-06-renta-cuota-chain-rollout-plan]]'
  - '[[2026-04-21-modelo-100-renta-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-research]]'
  - '[[2026-05-03-calculation-truth-inventory-research]]'
  - '[[2026-06-04-renta-cuota-chain-rollout-research]]'
---

# `renta-cuota-chain-rollout` adr

## Context

Modelo 100 already had partial income-side and settlement-side calculation
substrate, but the quota-chain middle was still manual. The rollout plan
expands that missing chain through the calculation registry rather than by
adding filing-grade legal logic back into Python modules.

## Decision

- Land the cuota-chain rollout entirely through typed registry substrate:
  legal references, parameters, formulas, bindings, and relations.
- Keep aspirational end-state tests strict so each delivered phase forces
  explicit review when it turns from expected-fail to pass.
- Treat multi-year registry coverage as part of the slice, not a later
  cleanup.

## Consequences

- Modelo 100 chain logic remains centralized in the registry substrate.
- Progress is measurable through honest, non-tautological calculation tests.
- Future quota-chain changes extend the same typed substrate instead of
  reintroducing bespoke Python formula logic.
