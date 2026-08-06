---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:3f65173b9f2e361c3da209a2e95b4a33116eebf3d40eae98199b9a8e6eeb69be'
step_id: 'S26'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Byte-compare the complete generated marketplace plugin tree with its source authority

## Scope

- `src/cadrumo/agent/tests/test_marketplace_generation.py`

## Description

- Run the marketplace byte-compare gate against the live source authority.
- Confirm the generated marketplace plugin tree is byte-compared with the
  authored agent-data source and the packaged wheel payload by the real
  generation tests, with no fixture or mock substitution.

## Outcome

- `src/cadrumo/agent/tests/test_marketplace_generation.py` passed 4/4 on
  2026-07-17 against the current source tree (48.8 seconds, real
  materialisation), proving the complete generated marketplace tree matches its
  source authority byte-for-byte. The same generation path produced the
  marketplace and plugin members of release cohort
  `616f48fcc2a748349cbfccb48952499523d3de82ad5ced1f5ec664b67024e16f` at source
  commit `044e48450e918648fd331072bda4767b47737d34`, and that generated
  marketplace installed and served correctly in the live plugin-install lane.

## Notes

- Implementation was landed by earlier campaign commits; this record closes the
  row on verification evidence produced by the plan owner.
