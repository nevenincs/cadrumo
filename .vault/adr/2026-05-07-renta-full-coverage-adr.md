---
tags:
  - '#adr'
  - '#renta-full-coverage'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - '[[2026-05-07-renta-full-coverage-plan]]'
  - '[[2026-05-07-renta-scope-audit-audit]]'
  - '[[2026-04-21-modelo-100-renta-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-research]]'
  - '[[2026-06-04-renta-full-coverage-research]]'
---

# `renta-full-coverage` adr

## Context

The renta scope audit quantified how little of Modelo 100 was honestly
covered and made the gap impossible to track with piecemeal slices alone.
The branch needed one feature-level decision that turns full coverage into
an explicit, auditable program instead of an informal aspiration.

## Decision

- Use one authoritative plan to sequence the full Modelo 100 coverage
  rollout across substrate, formulas, and audit refreshes.
- Measure progress by audit metrics and honest coverage gates rather than
  by raw casilla counts alone.
- Keep typed substrate, legal-binding discipline, and centralized backend
  ownership mandatory for every slice.

## Consequences

- Coverage work is coordinated against one durable roadmap instead of many
  disconnected featurelets.
- Audit refreshes become the contract for progress and regression.
- Full-coverage work inherits the same anti-tautology rules as the narrower
  renta calculation slices.
