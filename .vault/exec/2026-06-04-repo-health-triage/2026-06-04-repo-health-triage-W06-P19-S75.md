---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S75'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P19.S75 registry formula complexity reduction

Scope: `W06.P19.S75` - Reduce registry formula initial-value cognitive
complexity.

## Description

- Extract initial-value input rejection, previous-filing projection validation,
  and per-casilla value construction into private registry formula helpers.
- Extract M210 resolve-rate argument validation, baseline lookup, convenio row
  lookup, and convenio-rate parsing into private registry formula helpers.
- Preserve existing validation classes, translated messages, context keys, and
  M210 sentinel behavior.

## Outcome

Completed. `initial_values` no longer carries the initial-value validation flow
as one high-complexity function, and `_evaluate_m210_resolve_rate` no longer
owns argument validation plus both lookup paths inline.

Verification:

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_formula_initial_values.py`
  passed.
- `uv run --no-sync ty check src/aeat/domain/calculations/registry/_formula_runtime.py src/aeat/domain/calculations/registry/_formula_initial_values.py --output-format concise`
  passed.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_modelo_130_registry.py src/aeat/domain/calculations/registry/test_modelo_210_registry.py src/aeat/application/modelo/test_modelo_210_phase1.py -q`
  passed with 53 tests.
- `uv run --no-sync radon cc src/aeat/domain/calculations/registry/_formula_initial_values.py src/aeat/domain/calculations/registry/_formula_runtime.py -s`
  reported `initial_values` A (4) and `_evaluate_m210_resolve_rate` B (6).
- `uv run --no-sync complexipy src/aeat/domain/calculations/registry/_formula_initial_values.py src/aeat/domain/calculations/registry/_formula_runtime.py --max-complexity-allowed 20`
  passed with `initial_values` at 0 and `_evaluate_m210_resolve_rate` at 6.

## Notes

`calculate_registry_snapshot` remains a separate runtime orchestration hotspot
at Radon D (22). A broader M200 registry probe remains red because previous-filing
bound casilla `01494` requires an unresolved binding value; the S75 refactor did
not weaken or hide that exception.
