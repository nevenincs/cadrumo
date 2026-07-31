---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:0f9a57641da13146e307682c7ab3f84e0f7355d5ca21814ca33dcf9ed585e8d9'
step_id: 'S09'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Author docs/how-to/modelo-100.md as a condensed how-to cross-linking the Renta deep-dive for mechanism, with live-verified commands including the annual period token

## Scope

- `docs/how-to/modelo-100.md`

## Description

- Author `docs/how-to/modelo-100.md` as the condensed annual-Renta how-to:
  the "This page covers the ..." opening, the annual `0A` period token and
  per-year revision resolution, the dependency preflight (`aeat app modelo
  requires 100 --year 2025 --period 0A` and `aeat app modelo work
  dependencies`), the create/calculate/review/verify/export chain, the
  missing-bindings and manual-casilla workflow, and the file/reconcile tail.
  Deep mechanism is delegated to the new Renta explanation document
  (P03.S11) per the ADR.
- Ground against the live surface this session: `aeat app modelo describe
  100` (annual, `0A` only, revisions 2020-2025, 2239 casillas, 63 bindings,
  214 formulas - the annual token re-verified per open question #6),
  `aeat app modelo bindings list --modelo 100 --year 2025 --period 0A`
  (relation_prefill fold-ins from modelos 111/123/130/131/184/190/193,
  previous_filing negative-base carry, profile and renta ledger aggregation
  bindings), `aeat app modelo requires 100 --year 2025 --period 0A` (manual
  casilla inventory), and `aeat app modelo work dependencies --help`.
- Add the `modelo-100` toctree entry to `docs/how-to/index.md`.

## Outcome

The "How do I file my Renta?" question has a dedicated actionable page whose
mechanism depth lives in the companion explanation document.

## Notes

The page links to `../explanation/renta-and-bindings.md`, authored in
P03.S11 immediately after P02.S10; dangling for the span of two commits,
covered by the P05.S16 gate run.
