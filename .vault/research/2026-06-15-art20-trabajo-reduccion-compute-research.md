---
tags:
  - '#research'
  - '#art20-trabajo-reduccion-compute'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-06-15-art20-trabajo-reduccion-compute-adr]]'
---

# `art20-trabajo-reduccion-compute` research: investigation backing the decision

This research captures the investigation that backed the `art20-trabajo-reduccion-compute` ADR.

## Findings

Modelo 100 casilla `0023` ("Cuantía aplicable con carácter general") is the reducción
por obtención de rendimientos del trabajo of LIRPF art. 20. The legal-grounding campaign
corrected its `legal_refs` (art-17 → art-20) but the casilla remained a MANUAL input —
the operator transcribes the figure the AEAT program computes.

The reduction is a piecewise-linear function of the rendimiento neto del trabajo
(casilla `0022`) gated by an eligibility condition on the rest of the return, so
`no-silent-under-declaration` warns that leaving it a bare manual input can file an
under-declared return with zero operator signal. The art. 20 schedule was verified this
campaign against the bundled `ley-35-2006.html#a20`, the AEAT 2024 manual §7.1.6, and
RDL 4/2024 art. 3.1 (BOE-A-2024-12944). The investigation concluded `0023` should be
computed from `0022` behind its eligibility gate rather than transcribed.
