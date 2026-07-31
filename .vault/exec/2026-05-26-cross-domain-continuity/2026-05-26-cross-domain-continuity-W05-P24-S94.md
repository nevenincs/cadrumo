---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:5d6b03dcdb4eef434c21944e9ee922ff9baee4dabba10331524d3482df711257'
step_id: 'S94'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# wire new iva_category and counterparty_eu_member_state axes into IVA aggregation so Modelo 303 casillas 59 and 60 receive their bases

## Scope

- `casilla 62 EXCLUDED from scope (it is the criterio de caja box per art 75 LIVA not an intracom box)`
- `also handle the R12 nuance where B2B services to EU customers resolve to DOMESTIC_NOT_SUBJECT not INTRA_COMMUNITY_SUPPLY`
- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

- Ground the intracommunity and export route through the RAG index and the IVA classification-enrichment decision.
- Inspect the committed Modelo 303 registry bindings and the real aggregation scenario suite.
- Run the intracom/export and registry-binding tests plus Ruff.
- Obtain an independent code review of the registry authority, R12 boundary, counterparty gates, and cash-accounting exclusion.

## Outcome

The current implementation satisfies the required route without a parallel application helper. Registry bindings populate casilla 59 only for zero-rated repercutido intra-community supplies and casilla 60 for the two zero-rated export categories. R12 B2B services remain DOMESTIC_NOT_SUBJECT and do not feed casilla 59. Casilla 62 is confined to the independent cash-accounting four-box path. The focused suite passed 36 tests with Ruff, and independent review found no critical, high, or medium issue.

## Notes

The historical grouped S91-S95 record documented an earlier deferral. This individual record restores the direct evidence edge for the completed registry-owned implementation.
