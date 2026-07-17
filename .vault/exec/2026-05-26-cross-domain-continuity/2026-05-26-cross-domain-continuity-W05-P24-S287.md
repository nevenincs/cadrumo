---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S287'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-06-cross-domain-continuity-adr]]"
---

# FU-W05-B author IVA-category-and-counterparty ADR formalising the architect's four decisions: D1 field placement on Transaction not BusinessClassification, D2 no BusinessClassification extension, D3 casilla-62 criterio-de-caja scope exclusion, D4 R12 routing for B2B services to EU customer

## Scope

- `cite Ley 37/1992 articles 25 21 163 quinquies 75`
- `blocks S91 implementation`
- `.vault/adr/`

## Description

- Ran the mandated RAG searches for criterio de caja, casilla 62, LIVA art. 163,
  and Modelo 303 aggregation across code and vault documents.
- Reviewed the accepted IVA classification ADR, the cross-domain-continuity plan,
  and the May audit evidence for casillas 59/60/62.
- Cross-checked the bundled LIVA corpus for arts. 21, 25, 75, and the art. 163
  cash-accounting family against live BOE and AEAT official pages.
- Scaffolded and authored `2026-07-06-cross-domain-continuity-research`.
- Scaffolded and authored accepted ADR `2026-07-06-cross-domain-continuity-adr`.
- Updated S281 through the plan CLI so the pending implementation brief says
  cash accounting is an independent regime/payment-evidence axis, not an
  `IvaCategory` variant, and names the full 62/63/74/75 cash-accounting set.

## Outcome

S287 is closed. The accepted ADR preserves the existing intracom/export D1-D4
decision set from `2026-05-27-iva-classification-enrichment-adr` and adds the
missing S281 decision: criterio de caja is a timing/reporting regime with payment
evidence, not an operation category. S281 remains open for production
implementation.

## Notes

No production code was changed. Full vault check still reports pre-existing
modified-stamp warnings across thousands of unrelated vault documents; those were
not auto-fixed to avoid sweeping peer WIP.
