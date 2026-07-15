---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S12'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Author tutorials/irpf-lifecycle.md: setup, four quarterly Modelo 130 stages with cumulative carry, annual Modelo 100 close via cross-period fold-in, file and reconcile

## Scope

- `absorb the existing tutorials/index.md walkthrough as the first-quarter stage`
- `docs/tutorials/irpf-lifecycle.md docs/tutorials/index.md`

## Description

- Author `docs/tutorials/irpf-lifecycle.md`: the "This page covers the ..."
  opening, the named persona (Ana García López, consultora, activity start
  2026-01-01) shared with the IVA tutorial, and five stages - setup with the
  calendar/explain preview, the first quarter (absorbing the existing
  tutorial's verified command chain and its literal key-figure/verify
  output), the second and third quarters demonstrating cumulative behaviour
  (no binding zeros; carries resolve from the filed prior quarter; the
  cross-period blocked case explained), the fourth quarter closing the
  instalment year, and the annual Modelo 100 close with the dependencies
  preflight, missing-bindings check, and the deep-dive cross-link.
- Keep the mainline on-rails: no decision points; the file/reconcile rhythm
  repeats identically each quarter.
- Command surfaces re-verified live this session: modelo 130 binding ids and
  cumulative sources, modelo 100 `0A` token and fold-in bindings,
  `work dependencies` and `reconcile pull` syntax. Literal output
  transcripts appear ONLY where lifted from the pre-verified Q1 walkthrough;
  no output beyond Q1 was fabricated - later stages state expected behaviour
  in prose instead of quoting invented transcripts.
- `tutorials/index.md` conversion to the two-tutorial index rides P04.S14.

## Outcome

The IRPF lifecycle tutorial exists: one persona, one continuous ledger, four
instalments and the annual close, with the cumulative-carry behaviour as the
narrative spine.

## Notes

A full live-fire replay of the whole year (sandbox profile, all four
quarters plus the annual) was not run in this shared dev environment; the
honesty review (P05.S17) should weigh scheduling one as a follow-up
verification.
