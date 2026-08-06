---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:07186d99a1ac407e22fdc471e200f022b462bb63d73a48768b6b3e70d23b7f7c'
step_id: 'S12'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Make the plain pip lane consume supplied cohort artifacts without rebuilding

## Scope

- `dev/packaging/smoke_pip_core.py`

## Description

- Load the immutable Python cohort manifest and require all three local wheels.
- Install the root wheel and exact companion targets in one plain-pip transaction.
- Verify installed versions, direct artifact origins, and SHA-256 digests.

## Outcome

- The plain-pip lane consumes only the supplied cohort and never rebuilds or resolves a companion from an external index.
- Cohort, workflow, and release structural tests passed in the 55-test packaging gate.

## Notes

- Public PyPI reacquisition remains owned by S45.
