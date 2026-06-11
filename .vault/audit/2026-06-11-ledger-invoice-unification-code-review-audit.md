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
