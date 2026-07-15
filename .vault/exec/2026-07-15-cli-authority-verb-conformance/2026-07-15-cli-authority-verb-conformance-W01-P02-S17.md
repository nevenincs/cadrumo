---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S17'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Preserve the zero production-domain-to-adapters assertion and identify both test-only carveouts

## Scope

- `src/cadrumo/tests/test_importlinter_ledger.py`

## Description

- Define the two sanctioned layered domain-to-adapter test-carveout pairs exactly.
- Require observed layered domain-to-adapter pairs to remain a subset of that sanctioned set.
- Preserve the two-edge ceiling and the separate all-contract production hard-zero assertion unchanged.

## Outcome

The live layered inventory contains the sanctioned `cadrumo.domain.tests.**` and `cadrumo.domain.**.tests.**` sources, both targeting `cadrumo.adapters.**`. The subset assertion allows either debt edge to disappear while rejecting replacement or additional identities with an unexpected-pair diagnostic. The production inventory remains zero.

`ruff check` passed. The focused ledger module passed all five tests. A fresh uncached Import Linter run analyzed 3,421 files and 16,157 dependencies with all five contracts kept and none broken.

## Notes

No incidents or skipped verification.
