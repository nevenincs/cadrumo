---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S19'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Aggregation Source Invoice Alias Retirement

## Scope

C4 ledger invoice unification reconciliation for `P04.S19`.

## Description

- Removed `AggregationSourceKind.INVOICE = "invoice"` from `src/aeat/core/aggregation.py`.
- Kept `CounterpartSourceKind` constrained to the canonical source kinds.
- Updated the enum docstring with the source-search finding and the canonical invoice-family routing rule.

## Outcome

The core aggregation taxonomy no longer exposes a bare `invoice` source-kind alias.

## Verification

- `rg -n "AggregationSourceKind\.INVOICE" src/aeat` returned no matches.
- Focused aggregation/operator/registry gate passed: 203 tests.
- CLI documented-command and JSON schema conformance gate passed: 133 tests.
