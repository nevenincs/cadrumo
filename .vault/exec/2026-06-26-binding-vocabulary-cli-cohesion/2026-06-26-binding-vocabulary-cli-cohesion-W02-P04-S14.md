---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-30'
step_id: 'S14'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Verify W02.P04 no-shift: run pytest --collect-only -q clean, the aggregation / filing-runtime test modules green, and assert ModeloSourceResolver / CalculationSourceResolution / merge_source_resolutions were NOT renamed (the phase-2.2 settled contract is intact)

## Scope

- `src/aeat/application/aggregation/tests`
- `src/aeat/application/filing/tests`

## Description

- Assert the settled phase-2.2 `ModeloSourceResolver` protocol, `CalculationSourceResolution` envelope, and `merge_source_resolutions` aggregate are NOT renamed and still present at their original definitions in `_source_mesh.py`.
- Run the aggregation-service, source-mesh, source-resolver-enrollment, and filing-runtime test modules plus the bindings-framework gate suite.

## Outcome

W02.P04 no-shift proven. The settled resolver contract is intact (the protocol, the output envelope, and both merge functions all present at their original locations). collect-only clean (16463). The aggregation / mesh / enrollment tests ran 69 passed and the bindings-framework gate suite ran 49 passed (with the 98 across earlier W02 steps); the filing tests ran 230 passed under S13.

## Notes

None.
