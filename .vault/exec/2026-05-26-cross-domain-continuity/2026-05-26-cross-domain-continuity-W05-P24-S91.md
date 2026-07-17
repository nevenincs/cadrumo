---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S91'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# add iva_category IvaCategory and counterparty_eu_member_state EUMemberState fields directly on Transaction in domain transactions _models.py

## Scope

- `do NOT extend BusinessClassification with intracom export values per architect verdict`
- `IvaCategory already exists in domain iva _schema.py`
- `blocked on FU-W05-B ADR acceptance`
- `src/aeat/domain/transactions/_models.py`

## Description

- Reconciled the transaction IVA classification axis to the grouped Wave-5 execution evidence.
- Confirmed the reviewed record covers the S91–S95 implementation batch.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

S94 is handled separately because its grouped record documents a deferral rather than completion.
