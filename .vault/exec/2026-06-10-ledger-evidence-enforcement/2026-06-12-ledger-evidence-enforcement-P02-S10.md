---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S10'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P02.S10

Step `P02.S10` - Export the evidence advisory through the aggregation package boundary.

## Description

Confirmed `missing_evidence_advisory_observations` and `MISSING_TRANSACTION_EVIDENCE_SOURCE_KIND` are exported from `aeat.application.aggregation`.

## Outcome

Verification consumes the advisory through the application package boundary instead of importing from the private module.

## Notes

The exported function uses a public name rather than a private underscored name to match the package-boundary rule.
