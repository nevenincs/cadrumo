---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S18'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the repaired ignore-ledger tests and record the parsed 199, 78, and 2 inventory

## Scope

- `src/cadrumo/tests/test_importlinter_ledger.py`

## Description

- Run `uv run --no-sync pytest -q -n 0 src/cadrumo/tests/test_importlinter_ledger.py` to verify the repaired ledger suite serially.
- Import `_ignore_edges` from the codebase test module and derive the live inventories from its parsed records.
- Record total, layered, ratcheted, and production-hard-zero counts without editing source or test code.

## Outcome

The serial ledger suite passed all five tests in 1.19 seconds. The imported helper returned 265 total ignore edges and 229 layered edges: 199 application-to-adapter edges, 78 application edges targeting `cadrumo.adapters.**`, two layered domain-to-adapter edges, and zero production domain-to-adapter edges.

## Notes

No source or test file was changed. No incidents or skipped verification.
