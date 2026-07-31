---
tags:
  - '#exec'
  - '#ledger-invoice-unification'
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:0b1bd17a1ff41cb922daf589ce883818bc6b37daac1f1aef0101a53c4bd99a44'
step_id: 'S01'
related:
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---

# Invoice Source Alias Consumer Search

## Scope

C4 ledger invoice unification reconciliation for `P01.S01`.

## Description

- Re-ran the `AggregationSourceKind.INVOICE` consumer search across `src/aeat`.
- Promoted the finding into the `AggregationSourceKind` docstring while retiring the member.
- Confirmed residual `source="invoice"` literals are rejection tests only.

## Outcome

No production `src/aeat` consumer still references `AggregationSourceKind.INVOICE`; the bare invoice alias is no longer load-bearing.

## Verification

- `rg -n "AggregationSourceKind\.INVOICE" src/aeat` returned no matches.
- `rg -n 'source\s*=\s*"invoice"|"source":\s*"invoice"|source_kind\s*=\s*"invoice"' src/aeat --glob '!**/tests/**'` returned no matches.
