---
step_id: S325
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S325 — relocate AggregationSourceKind to aeat.core.aggregation

## Outcome

Created `src/aeat/core/aggregation.py` with `AggregationSourceKind` (StrEnum, 4 members: `LEDGER_TRANSACTION`, `PURCHASE_INVOICE_EVIDENCE`, `PAYABLE_INVOICE`, `COLLECTIBLE_INVOICE`). Uses `get_logger` from `aeat.core.logging`.

## Files touched

- `src/aeat/core/aggregation.py` (new)

## Verification

Module imports cleanly. `AggregationSourceKind.__module__ == "aeat.core.aggregation"` confirmed by S327 test suite.
