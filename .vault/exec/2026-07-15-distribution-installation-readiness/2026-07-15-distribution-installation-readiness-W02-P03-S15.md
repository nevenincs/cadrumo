---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S15'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Correct the all-extras product identity gate and run real installed behavior

## Scope

- `dev/packaging/smoke_extras.py`

## Description

- Install the complete supplied cohort with every declared optional extra.
- Require the canonical Cadrumo product and executable identities.
- Exercise real installed CLI behavior and verify exact companion origins.

## Outcome

- The all-extras lane consumes the same immutable cohort as the other command-bearing lanes.
- Product identity and real installed behavior are covered by the focused packaging gate.

## Notes

- Client-specific Claude and MCPB installation remain open in later phases.
