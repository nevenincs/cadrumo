---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S07'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Anti-tautology test — internal_only=True + non-empty export_refs raises

## Scope

- `src/aeat/domain/calculations/registry/test_internal_only_casilla.py`

## Description

Authored `test_internal_only_casilla_rejects_non_empty_export_refs` in a new test module. The test constructs a `CasillaDefinition(internal_only=True, export_refs=("modelo-200-2024:DP200014:00552",), input_kind=COMPUTED, ...)` and asserts a `ValidationError` is raised matching "internal_only". Pydantic v2 wraps the `RegistryValidationError` raised inside the validator into `ValidationError`; the matching pattern follows the established convention in `test_schema.py`.

## Outcome

The mis-declaration shape (claimed app-internal but exported to a fichero record) is structurally proven to be refused at load. The test is a real-behavior assertion against the validator contract, not a hand-computed calculation expectation, so the `no-tautological-calculation-tests` rule is satisfied.
