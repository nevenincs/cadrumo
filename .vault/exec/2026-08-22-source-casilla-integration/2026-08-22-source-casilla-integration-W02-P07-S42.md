---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:99ce010e4dacb8890d52d411b6e1c1d30a5ab7257ac903a4f980c61d762caed5'
step_id: 'S42'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enforce inventory source ownership and caller-override refusal

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Add inventory to the canonical deterministic source-ownership lock ladder.
- Derive binding and bound-casilla collisions from registry selectors through the existing calculation guard.
- Refuse equal, different, partial, complete, and alias caller substitutions while preserving undeclared manual input.
- Update conformance truth and add replay-stable ownership tests.

## Outcome

Inventory is now a deterministic source-owned family in the single canonical caller-override precedence ladder. The calculation policy derives its lock set from that ladder, and the existing calculation guard derives exact owned binding and bound-casilla identities from the active registry revision. Caller values therefore cannot collide with, replace, shadow, or silently equal an inventory-derived output.

The policy contains no hard-coded inventory casilla map. When a revision does not declare inventory bindings, its manual casillas remain available under the standing absence policy. Non-canonical aliases refuse at registry input validation before ownership matching, and repeated identical requests produce the same typed, value-free outcome.

Independent review reported zero findings. Twenty-one focused tests passed, and Ruff, the focused type checker, and scoped diff hygiene were clean.

## Notes

Grounding showed that the plan's `_calculate_input.py` target was not the policy authority: it parses typed channels but has no source-ownership context. The approved implementation redirected to `_source_mesh.py::CALLER_OVERRIDE_PRECEDENCE_LADDER`; `_calculation_source_policy.py` and `_calculation_actions.py` already project and enforce that single home. No `_calculate_input.py` edit or S43 binding data was added.

An exploratory existing `test_actions` source-bound fixture is red because its IVA selector omits newer required fields; a broader M349 exploratory failure was also unrelated. Neither belongs to S42, and both were left untouched.
