---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S08'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P02.S08

Step `P02.S08` - Integrate missing-evidence diagnostics into revision verification.

## Description

Confirmed `verify_modelo_revision` loads the revision source transactions, calls the aggregation package evidence advisory function, and appends each diagnostic as an advisory `ModeloVerificationFinding`.

## Outcome

Modelo verification now surfaces missing transaction evidence while preserving verified-complete eligibility when no blocking findings exist.

## Notes

The integration imports the advisory through `aeat.application.aggregation`.
