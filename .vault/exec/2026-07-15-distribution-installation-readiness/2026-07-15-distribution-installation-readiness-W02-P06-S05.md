---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Prove cohort construction is deterministic complete and non-rebuilding

## Scope

- `dev/packaging/tests/test_release_cohort.py`

## Description

- Prove cohort construction is deterministic, complete, and non-rebuilding
  through the real integration gate.
- Run the reproducibility integration test that builds the release cohort
  twice from clean archives of the same commit and compares the frozen
  digests, and confirms consuming lanes accept the stored bytes without any
  rebuild.

## Outcome

- `dev/packaging/tests/test_release_cohort_integration.py` passed (1/1,
  586 seconds) on 2026-07-17 at source commit
  `044e48450e918648fd331072bda4767b47737d34`: two independent clean-archive
  builds produced identical member digests, and the loaded cohort re-verified
  every artifact size and SHA-256 against its manifest without rebuilding.
- The unit-scope gates passed 5/5 in the same session across
  `dev/packaging/tests/test_python_cohort.py` (2 tests) and
  `dev/packaging/tests/test_release_cohort.py` (3 tests: hermeticity,
  portable paths, undeclared-file refusal) combined.

## Notes

- Determinism holds under the pinned build identity (CPython 3.13.11,
  uv 0.11.29, fixed source epoch and hash seed). The CI packaging workflows
  were pinned to the same uv version in commit `363213aee0` after the hosted
  runner's unpinned uv broke installed-digest provenance.
