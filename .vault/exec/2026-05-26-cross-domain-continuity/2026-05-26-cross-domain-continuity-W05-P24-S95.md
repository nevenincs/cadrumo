---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S95'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# regression test that an autonomo with intra-community GOODS supply (INTRA_COMMUNITY_SUPPLY iva_category, counterparty_eu_member_state set to a non-ES EU state) populates casilla 59 correctly

## Scope

- `anti-tautology proof mutating counterparty_eu_member_state to ES triggers DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION rejection`
- `separate scenario for DOMESTIC_NOT_SUBJECT (R12 B2B services like Marc IT to DE) confirms it does NOT feed casilla 59 per ADR D4`
- `src/aeat/application/aggregation/test_intracom_export.py`

## Description

- Reconciled the intracom aggregation regression coverage to the grouped Wave-5 execution evidence.
- Confirmed the reviewed record covers the S91–S95 implementation batch.
- Added this per-step execution record without changing production sources.

## Outcome

The historical evidence supports the checked row. This record restores the one-Step, one-record traceability edge.

## Notes

S94 is handled separately because its grouped record documents a deferral rather than completion.
