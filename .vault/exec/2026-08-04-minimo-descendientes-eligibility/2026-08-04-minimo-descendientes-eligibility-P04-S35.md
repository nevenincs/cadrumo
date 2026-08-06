---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fa8bffda968d734a595b7438b0439d92e66ece3bc870dee61f5bc543b34a1764'
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

The row is CLOSED as a measured non-defect, not implemented and not deferred. The originating row's premise — that 0611 could reach parity with 0613 by becoming registry-computed — does not survive contact with 0613's actual formula: 0613 is a flat-rate-times-count pattern with no per-child cap variation, while 0611 after the alta-posterior increment has a cap that genuinely varies by which child carries it. The two casillas do not share a rule shape, so "parity" was never an achievable target, and two different rule shapes carried by two different mechanisms (registry formula for 0613, Python resolution for 0611) is what correct modelling looks like rather than an asymmetry to fix. The only route to genuine registry computation of 0611 — a new aggregation primitive applying a conditional per-row cap — would exist purely for auditability, since the figure the current Python computation produces is already correct; nothing in the research found an incorrect figure or a hidden defect, only an unreachable resemblance.

This closure is recorded in the governing ADR's consequences section as a decision with a stated reopening condition, and in the plan as a closed step, both citing the same reasoning captured here.

## Notes

This is a closure, not a deferral, and not a scope narrowing. The original row's completion criterion — achieve registry-computed parity with 0613 — was not judged too expensive to pursue; it was measured false, because the premise the criterion assumed (shared rule shape) does not hold. A campaign closing a step by judging a true criterion not worth meeting would be scope narrowing; this step closes because the criterion itself rested on a false premise, which research disproved rather than argued around.

The recorded reopening condition: if a future legal reform makes casilla 0611's per-child cap uniform again (removing the alta-posterior increment's per-child variation), the parity premise with 0613 would genuinely hold again, and this decision should be revisited on that basis rather than cited as a permanent closure.

This record was authored by the agent that performed the research, overwritten by the coordinator while that agent was session-limited, and restored here. The overwrite was a process error: a paused agent resumes rather than dies, and its work is not the coordinator's to replace.
