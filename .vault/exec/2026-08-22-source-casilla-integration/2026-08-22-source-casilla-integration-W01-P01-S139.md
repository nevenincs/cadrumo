---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:63ba5ec2a3748688d86ce99d0b060895604a6495f78811ec415e507d237aa1bb'
step_id: 'S139'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# align connected source-reference validation exactly with persisted CalculationSourceRef semantics

## Scope

- `src/cadrumo/core`

## Description

- Define a purpose-specific opaque persisted source-reference constraint.
- Align connection and encrypted-proof identities with the authoritative 1–256 character domain.
- Preserve case, punctuation, and surrounding whitespace byte-for-byte.
- Compare accepted and rejected boundaries directly with `CalculationSourceRef`.

## Outcome

Connectivity proof can now represent every value accepted by the canonical
persisted `source_ref` field without normalization. Equality remains literal,
so any case, punctuation, namespace, spacing, or content mutation is refused.

## Notes

The new constraint is private and purpose-named; no additional public facade
symbol or compatibility surface was introduced.
