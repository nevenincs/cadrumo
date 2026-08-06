---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:2447871d838e51cce1e0d288101c1a6e247ce019eb656afbf5d5c3525dc42e5e'
step_id: 'S13'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Make the sdist lane consume the supplied cohort and verify its resolved companions

## Scope

- `dev/packaging/smoke_sdist_core.py`

## Description

- Build the compact root source distribution as a member of the clean cohort.
- Install that sdist together with both supplied companion wheels.
- Assert exact companion pins, local origins, digests, and installed command behavior.

## Outcome

- The sdist lane consumes the supplied cohort without external companion resolution.
- Real artifact tests prove the root sdist excludes companion corpus payloads while retaining the command-bearing source.

## Notes

- Full public-index reacquisition remains owned by S45.
