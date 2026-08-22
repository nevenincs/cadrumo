---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:9261a25c7f4243421505387cad1ee3f9b605a60594dff68588eaa55ae60bc3b5'
step_id: 'S05'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# verify invalid dispositions, incomplete blocked rows, expired review conditions, and unsupported connected claims are refused

## Scope

- `src/cadrumo/core/tests/test_source_connectivity.py`

## Description

- Exercise the complete S01-S04 contract only through the public `cadrumo.core` facade.
- Refuse unknown dispositions, malformed candidate identities, and unfetchable grounding locator shapes.
- Refuse incomplete blocked, connection-candidate, and manual-by-design rows.
- Prove deterministic expiry boundaries, finite follow-up deadlines, and explicit or inherited ownership.
- Mutate every relational proof identity and refuse unrelated or wrongly scoped executable evidence.
- Refuse coercible and false proof assertions, authority-free connected claims, deferred sources, unsupported commands, and absent or changed evidence.
- Prove the complete supported authority path and the facade export inventory.

## Outcome

The focused core suite contains 34 passing tests over the complete connectivity
contract. Every fail-closed state assigned to this phase is executable, including
the live-authority boundary that prevents a shape-valid but unsupported
`connected` claim. The suite imports no private connectivity implementation.

## Notes

Ruff, compilation, and focused pytest passed. The first relational-mismatch
assertion expected the aggregate validator message, while the stricter nested
evidence validator refused the mutation earlier. The assertion now accepts both
legitimate refusal layers; no production change was required. Tests use fixed
dates and explicit authority inventories, with no ambient clock, filesystem, or
network dependence.
