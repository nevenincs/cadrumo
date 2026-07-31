---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:d31ae34a7952f02177ab97c3547949f43ea898da21c39825cb30e6e9ecb6080f'
step_id: 'S11'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

# Author explanation/renta-and-bindings.md: the labelled deep-dive on how the Renta filing builds from the ledger, the Modelo 130 fold-in, profile facts, registry bindings, cross-period carry, and visible-gaps-not-guessed-zeros

## Scope

- `ground every command against the live bindings/dependencies/observations surface`
- `docs/explanation/renta-and-bindings.md`

## Description

- Author `docs/explanation/renta-and-bindings.md` as the sanctioned
  deep-dive: explicitly labelled as the one command-dense explanation page,
  with the "This page covers the ..." opening. Sections: the four source
  kinds (profile facts, ledger aggregations, prior-filing fold-ins, prior
  Renta carry) keyed to the live binding listing; the evidence-gated
  quarterly fold-in with the `work dependencies` preflight and the
  scoped-out-not-silently-skipped rule; the visible-gaps-not-guessed-zeros
  design rule; the cross-year negative-base carry with its revision
  re-confirmation guard; and figure-to-law tracing via `work observations`,
  `work revision`, and per-casilla JSON `legal_refs`/`source_refs`.
- Ground every named command against the live surface this session:
  `bindings list --modelo 100 --year 2025 --period 0A` (profile / ledger /
  relation_prefill / previous_filing sources quoted), `requires 100`,
  `work dependencies --help`, `work observations` (verb existence via the
  operator surface).
- Cross-link the page from `explanation/index.md` (new pointer paragraph
  under "When a form builds on earlier ones" and toctree entry).

## Outcome

The dedicated Renta document the operator mandated exists in the
explanation quadrant, labelled as a deep dive, and is the mechanism
counterpart to the condensed `modelo-100.md` how-to. Phase P03 complete.

## Notes

The IRPF lifecycle tutorial (P04.S12) links here from its annual-close
stage when authored.
