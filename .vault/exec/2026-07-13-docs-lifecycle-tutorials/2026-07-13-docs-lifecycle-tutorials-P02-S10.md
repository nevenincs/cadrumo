---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S10'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Author docs/how-to/modelo-349.md covering the intra-community recapitulative flow with live-verified commands

## Scope

- `docs/how-to/modelo-349.md`

## Description

- Author `docs/how-to/modelo-349.md`: the "This page covers the ..."
  opening, the pure-listing nature (zero formulas, summary block plus
  per-operator and rectification detail rows), the invoice-record-driven
  workflow (issued invoices feed entregas, received feed adquisiciones), the
  VIES `aeat app live verify nif-iva` pre-check, the standard
  create/calculate/verify/export chain, the rectification-of-earlier-period
  section, and the keep-303-and-349-consistent-via-records guidance.
- Ground against the live surface this session: `aeat app modelo describe
  349` (profile_based cadence, periods 01-12 and 1T-4T, 13 casillas, 34
  bindings, 0 formulas) and `aeat app modelo bindings list --modelo 349
  --year 2026 --period 1T` (collectible_invoice / payable_invoice sources,
  declarante summary and operador/rectificacion row binding ids) plus
  `aeat app modelo casillas 349 --period 1T` (detail-row field labels).
- Add the `modelo-349` toctree entry to `docs/how-to/index.md`.

## Outcome

All three Tier-1 modelo gaps (130, 100, 349) named by the operator now have
dedicated actionable pages. Phase P02 complete.

## Notes

None.
