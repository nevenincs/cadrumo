---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:c5f700dd9cde9806df753108ccd4437593377ef52f2aca71859164ef251b02e0'
step_id: 'S35'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Close the 0611 registry-computed question as a measured non-defect rather than implementing it, because 0613 is a flat-rate-times-count formula whose cap never varies per child while 0611 after the increment has a per-child varying cap, so the two casillas do not share a rule shape and parity was never achievable, and the only route to genuine registry computation is a new aggregation primitive applying a conditional per-row cap whose entire value is auditability since the figure is already correct

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/`

## Description

- Read the original row's premise: make casilla 0611 registry-computed like its 0613 sibling, since the engine now derives every term it needs.
- Read 0613's actual registry formula rather than assuming parity from its label: a single `min` over three scalars, one of which is a flat per-child rate (€1.000) multiplied by a scalar count of eligible children. Every eligible child contributes the identical amount; the cap never varies per child.
- Read 0611's arithmetic after the alta-posterior increment: the per-child cap is €1.200 or €1.350 depending on whether that specific child carries the increment, so one filing can have children under two different caps at once.
- Read the closed `BindingAggregationOp` set (`sum`, `rows`, `copy`, `count_distinct`, `prior_pagos_fraccionados`) and the formula-expression operator set (fixed-arity `add`/`subtract`/`multiply`/`divide`/`percent`/`min`/`max`/`clamp`/`negate`, no per-row iteration construct) and confirmed neither can express a per-row conditional cap selection followed by a fold.
- Read an existing profile-sourced detail-record consumer end to end (a sibling modelo's attribution-member resolver) to establish that a detail-record route would not, by itself, force a new operator-facing entry burden — the same persisted per-child facts already declared today could feed a resolver of that shape with no change to the declaration surface.
- Searched the registry for any existing casilla computing a genuine per-item-varying capped sum; found none. The assumed sibling does not demonstrate the pattern it was assumed to demonstrate.
- Reported findings, not a recommendation, including the tension the findings surface: a profile-sourced detail-record resolver would still require the per-child cap to be selected and applied in Python before the row enters the registry, so folding those rows would be cosmetically registry-computed while the legal cap rule stays one layer further from view than it is today — the same objection that barred the single collapsed `copy` alternative, recurring per row instead of collapsed to one scalar.

## Outcome

The earlier non-defect closure is reversed. Sol's architecture review established that its
premise described 0613's final registry formula while ignoring the variable per-child Python
fold that produces the derived scalar consumed by that formula. M100/2024 casilla 0611 shares
that architectural shape and is authorized to become registry-computed without a new
aggregation primitive: canonical per-child fold, derived profile scalar, `profile/copy`
binding, and binding-leaf formula.

The governing ADR now records the required invariant and the revision boundary. This Step is
a decision closure, not implementation proof. A separate implementation Step owns the 2024
producer, removal of the manual casilla-input path, source/legal provenance, official oracles,
and calculate/pull convergence. Revisions 2020-2022 remain blocked on year-parameterized
cotizaciones facts; 2023 and 2025 require separate enrollment and proof.

## Notes

The corrected ruling was independently validated against the focused 0611 and 0613 domain
suites: 63 tests passed. It also identifies the existing defect boundary explicitly:
`_calculate_input.py` currently injects the derived 0611 result through the manual
casilla-input channel, which omits registry formula provenance and leaves manual fallback
reachable. No implementation-complete claim is made here.

This record was authored by the agent that performed the research, overwritten by the coordinator while that agent was session-limited, and restored here. The overwrite was a process error: a paused agent resumes rather than dies, and its work is not the coordinator's to replace.
