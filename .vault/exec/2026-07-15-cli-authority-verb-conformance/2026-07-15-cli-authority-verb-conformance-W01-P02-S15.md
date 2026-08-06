---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:d72f7843a7cf56a0be470a238375460df3631b196125ff46cc52e5de212d7b01'
step_id: 'S15'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Freeze the domain test-edge ceiling at 2

## Scope

- `src/cadrumo/tests/test_importlinter_ledger.py`

## Description

- Lower `_DOMAIN_TO_ADAPTERS_BASELINE` from the obsolete 70 ceiling to the reconciled live count of two.
- Replace the historical increment note with the decrease-only test-carveout policy.
- Preserve explicit carveout identity and inventory non-vacuity for their separately planned steps.

## Outcome

The imported ledger helper reports exactly two layered domain-to-adapter edges, equal to the new ceiling, and zero production domain-to-adapter edges.

`ruff check` passed. The focused ledger module passed all four tests. A fresh uncached Import Linter run analyzed 3,421 files and 16,157 dependencies with all five contracts kept and none broken.

## Notes

No incidents or skipped verification.
