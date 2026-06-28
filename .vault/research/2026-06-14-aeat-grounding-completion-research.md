---
tags:
  - '#research'
  - '#aeat-grounding-completion'
date: '2026-06-14'
modified: '2026-06-14'
related:
  - '[[2026-06-14-aeat-grounding-completion-adr]]'
---

# `aeat-grounding-completion` research: investigation backing the decision

This research captures the investigation that backed the `aeat-grounding-completion` ADR.

## Findings

The legal-grounding verification swarms confirmed the codebase's regulatory figures are
overwhelmingly correct and centralized, but surfaced a distinct class of findings: not
wrong values or mis-placed literals, but legitimately MISSING features — real
Spanish-tax law the application should model but does not yet.

The missing features differ in kind and risk: (a) missing registry data a gate would
consume (the estimación-objetiva módulos magnitude-exclusion limits; the IS Entidad de
Reducida Dimensión INCN<10M transitional schedule) — low-risk registry authoring with a
clear legal basis; and (b) a display-echo limitation where the underlying tax is already
correct (the M200 casilla `00558` two-tranche micro-empresa rate echo). The
investigation concluded that, per the operator directive, legitimately-missing features
are in scope to BUILD (not merely track), each grounded against its BOE/AEAT source.
