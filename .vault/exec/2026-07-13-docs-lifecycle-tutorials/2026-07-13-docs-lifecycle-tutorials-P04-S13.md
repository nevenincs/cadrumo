---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S13'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Author tutorials/iva-lifecycle.md: setup with optional prorrata, quarterly Modelo 303 stages with IVA-wallet seed and credit carry, optional Modelo 349 branch, annual Modelo 390 reconciliation, file and reconcile

## Scope

- `same persona and continuous dataset as the IRPF tutorial`
- `docs/tutorials/iva-lifecycle.md`

## Description

- Author `docs/tutorials/iva-lifecycle.md`: the "This page covers the ..."
  opening; the shared persona and continuous ledger explicitly continued
  from the IRPF tutorial (same rows carry the IVA detail); five stages -
  the opening IVA-wallet seed with the correction path and the
  consumed-by-filed-return refusal guard, the first paying quarter, a
  credit quarter and the carry demonstrated via `iva-wallet balance`, the
  clearly-marked optional Modelo 349 intra-community branch, and the annual
  Modelo 390 close with its quarters-must-reconcile blocking rule.
- Verify the wallet surface live this session: `aeat app modelo iva-wallet
  --help` (balance/seed/correct/override semantics, including the
  filed-consumption refusal and `--reason`/`--confirm` requirements) and
  `aeat app modelo describe 390` (annual `0A`, 22 casillas, 17 bindings).
  The 303 chain and wallet seed commands match the existing verified
  modelo-303 how-to.
- Land the deferred final trim from P01.S07: the IVA-wallet prose in
  `explanation/building-on-earlier-filings.md` now points at the tutorial
  as its live demonstration.
- No literal output transcripts were fabricated; behaviour beyond the
  verified surfaces is stated in prose.

## Outcome

The IVA lifecycle tutorial exists, the wallet workflow finally has an
actionable home (closing the phase-1 real-gap finding), and the two
tutorials share one persona and dataset as the ADR ratified.

## Notes

Same live-fire caveat as P04.S12: a full-year sandbox replay is a
follow-up candidate for the honesty review.
