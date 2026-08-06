---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:c651c3c3b8780a2eb488e6519732a721f69d224ae69d6f0798d0ecdc4c93c7d8'
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
