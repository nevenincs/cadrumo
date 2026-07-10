---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S41'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Record whether namespace hash scans or transaction serialization dominate mutation latency

## Scope

- `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md`

## Description

- Re-ground the write-path attribution through semantic code and vault search.
- Read the S40 exec record and reference before editing.
- Append a W05.P13 write-path attribution section to the reference.
- Record the namespace hash scan, serialize+hash, and real one-row save timings.
- State the dirty-set/cache implication for follow-up design.

## Outcome
- `.vault/reference/2026-07-06-ledger-perf-optimization-reference.md` now records the S40 write-path attribution.
- The reference concludes that all-row transaction serialization plus SHA-256 dominates the named residual: P95 `1.399s`, about `7.0x` the namespace hash scan P95 `0.201s`.
- The reference records the real single-transaction save P95 as `2.659s` and frames dirty-set/cache design around avoiding all-row envelope serialization and payload hashing.

## Notes

- Semantic code search returned the new scale benchmark node, `namespace_payload_hashes`, `_serialise_transaction`, and the `_reconcile` loop.
- Semantic vault search returned the active S41 plan row, S40 exec record, research finding F6, and prior write-path reference text.
- No runtime code changed in this step.
