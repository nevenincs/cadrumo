---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:143881cb4149a1bd164fbf34df434be6776e9ec79b1614f25b3c0be13e0daf7f'
step_id: 'S08'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Author docs/how-to/modelo-130.md on the modelo-303 template with live-verified commands and the this-page-covers opening

## Scope

- `docs/how-to/modelo-130.md`

## Description

- Author `docs/how-to/modelo-130.md` on the modelo-303 template shape: the
  "This page covers the ..." opening, the complete verified first-quarter
  chain (profile, two ledger rows, create/calculate/verify/export with the
  three first-period zero bindings), the what-it-calculates section keyed to
  the live casilla table, and a dedicated "Each quarter is cumulative"
  section explaining the year-to-date ledger windows and the three
  `previous_filing` carries with the do-not-pass-zeros-later rule.
- Ground against the live surface this session: `aeat app modelo describe
  130` (quarterly, periods 1T-4T, 20 casillas, 8 bindings), `aeat app modelo
  casillas 130 --period 1T` (casilla ids/labels/input kinds quoted), and
  `aeat app modelo bindings list --modelo 130 --year 2026 --period 1T`
  (binding ids and sources quoted verbatim). The command chain is lifted from
  the existing verified tutorial walkthrough.
- Add the `modelo-130` toctree entry to `docs/how-to/index.md` (grid-card
  regrouping rides P05.S15).

## Outcome

The operator-named "How do I file my Modelo 130?" question now has a
dedicated actionable page, cross-linked to the tutorial, the filing spine,
and the future modelo-100 page.

## Notes

The page links to `modelo-100.md`, authored in the next step (P02.S09); the
link is dangling for the span of one commit and is covered by the P05.S16
gate run.
