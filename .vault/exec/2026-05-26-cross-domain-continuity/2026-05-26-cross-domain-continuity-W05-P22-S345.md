---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S345'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ANDREA-HIGH ledger preflight false-positives on nómina entries

## Scope

- `irpf_category=trabajo implies IVA exemption but preflight marks missing_taxable_base + missing_iva_amount + missing_iva_rate for every INCOMING with category trabajo`
- `teach preflight that trabajo entries are exempt from IVA validation`
- `src/aeat/application/ledger/_preflight.py`

## Description

- Reconciled the payroll IVA-preflight correction to its landed evidence.
- Confirmed `7b92f1a7d0` supplied the reviewed implementation.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

Historical evidence predates the current per-step record convention.
