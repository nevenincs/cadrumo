---
tags:
  - '#audit'
  - '#ledger-invoice-unification'
date: '2026-06-11'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
  - '[[2026-06-10-ledger-invoice-unification-adr]]'
  - '[[2026-06-10-ledger-invoice-unification-research]]'
---

# `ledger-invoice-unification` Code Review

## C4-ALIAS-001 | LOW | Cross-edit registry snapshot method indentation corrected

Review of the scoped C4 alias-retirement diff found a concurrent edit in `_schema.py` that had placed `verification_policy` under `filing_period_from_scope` instead of keeping it on `RegistrySnapshot`. The issue was corrected before commit. Follow-up lint, focused registry/operator tests, API-stub check, and CLI conformance gates passed.

## C4-ALIAS-002 | INFO | No open C4 alias-retirement findings

The bare `AggregationSourceKind.INVOICE` member and production references are removed. Remaining `source="invoice"` literals are rejection tests. Full-tree collect-only is still blocked by unrelated peer support-module import errors and remains tracked by `P04.S24`.

## C4-CLOSE-003 | INFO | P04.S24 closeout diff reviewed with no open findings

Review scope was the `P04.S24` plan closure and exec-record update. The full `src/aeat` collect-only gate now exits 0 with `15101/16882` collected and `1781` deselected, and the focused split-support collection guard exits 0 with `582` collected. The only caveat is operational: the vault plan step CLI closed `S24` but exited 1 during cache invalidation because its workspace context variable was unset; the plan row was verified closed afterward.
