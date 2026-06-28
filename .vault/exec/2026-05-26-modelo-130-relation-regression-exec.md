---
tags:
  - '#exec'
  - '#modelo-130-relation-regression'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S01'
related:
  - "[[2026-05-26-modelo-130-relation-regression-plan]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
---

# `modelo-130-relation-regression` `P01.S01`

Added the `max_year_delta` field to `_PreviousModeloSelector` with a
pydantic field validator rejecting negative values. The field is
optional (default `None`); when set, it caps the absolute value of
the resolver's returned `period_year_delta`. No anchor-drop behaviour
yet — that lands in `S02`. The field is dormant until the resolver
consults it.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`

## Description

`_PreviousModeloSelector` (line ~302) gained `max_year_delta: int | None = None` immediately after the existing `relation` field, with a TOML-comment block documenting the same-ejercicio rule from AEAT's Modelo 130 art. 110.5 instruction and the intended `0` value for that case.

A field validator `_max_year_delta_non_negative` rejects negative integers with `RegistryValidationError("previous-filing max_year_delta must be non-negative")`. The default of `None` preserves the unbounded behaviour and is the safe shape for every existing binding declaration.

No call site reads the field in this commit. `required_period_anchors_for_target`, `previous_filing_observation_requirements`, and `resolve_previous_filing_binding_values` continue to operate on the pre-S01 contract. The field is a pure schema addition; the runtime cap-drop behaviour lands in `P01.S02`.

## Tests

Smoke verification via direct construction (5 cases):

- `max_year_delta` unset → field is `None`, prior selector behaviour preserved.
- `max_year_delta = 0` → field validates and stores.
- `max_year_delta = 2` → field validates and stores.
- `max_year_delta = -1` → field validator raises `RegistryValidationError` naming `max_year_delta`.

Regression suite run (`pytest src/aeat/domain/calculations/registry/test_formula_runtime.py src/aeat/domain/calculations/registry/test_cross_dependency_contract.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py src/aeat/domain/calculations/registry/test_modelo_130_registry.py`): **48 passed in 63.47s, 0 failures**. The field addition is non-breaking against the existing binding population.

Dedicated unit tests for the field land in `P01.S03` after `S02` wires the resolver to honour the cap.
