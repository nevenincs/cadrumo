---
tags:
  - '#exec'
  - '#ledger-evidence-enforcement'
date: '2026-06-12'
step_id: 'S06'
related:
  - '[[2026-06-10-ledger-evidence-enforcement-plan]]'
---

# Ledger Evidence Enforcement P02.S06

Step `P02.S06` - Add missing-evidence advisory diagnostics for outgoing business expenses.

## Description

Confirmed `missing_evidence_advisory_observations` emits `CalculationSourceDiagnostic` rows for active, positive, outgoing business or mixed rows with cuota-bearing IVA classification and no purchase invoice evidence or attachment ids.

## Outcome

Evidence-less deductible business expense rows now produce non-blocking diagnostics.

## Notes

The implementation uses real `Transaction` models and avoids formula-derived expected values.
