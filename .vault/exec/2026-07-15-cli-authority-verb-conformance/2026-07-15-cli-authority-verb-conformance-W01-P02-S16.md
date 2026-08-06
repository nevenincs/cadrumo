---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:30c860fcc5b86222a6c37ff47ebf7dbeb96bf1862b79aa44ac5dff5611eb4f82'
step_id: 'S16'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Assert the parsed Cadrumo ignore inventory and layered-contract inventory are non-empty

## Scope

- `src/cadrumo/tests/test_importlinter_ledger.py`

## Description

- Add a focused test that requires both the parsed ignore ledger and its layered-contract subset to be non-empty.
- Diagnose parser-prefix drift separately from layered contract-name or configuration drift.
- Keep the test decrease-tolerant by avoiding exact total and layered inventory counts.

## Outcome

The real fixtures currently expose 265 parsed ignore edges and 229 layered edges. The new test guards those inventories against becoming empty without turning their reducible debt totals into fixed baselines.

`ruff check` passed. The focused ledger module now passes all five tests. A fresh uncached Import Linter run analyzed 3,421 files and 16,157 dependencies with all five contracts kept and none broken.

## Notes

No incidents or skipped verification.
