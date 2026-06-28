---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S08'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Anti-tautology test — internal_only=True + input_kind=MANUAL raises

## Scope

- `src/aeat/domain/calculations/registry/test_internal_only_casilla.py`

## Description

Authored `test_internal_only_casilla_rejects_non_computed_input_kind` alongside S07. The test constructs a `CasillaDefinition(internal_only=True, input_kind=InputKind.MANUAL, ...)` and asserts a `ValidationError` is raised matching "internal_only". A bookend `test_internal_only_casilla_accepted_when_computed_and_no_exports` proves the validator is not a blanket refusal: a formula-derived ceiling with no `export_refs` loads cleanly.

## Outcome

The mis-declaration shape (claimed app-internal but not formula-derived) is structurally proven to be refused at load. With the bookend test the validator's discipline is symmetrically defended: it rejects the two incoherent shapes and accepts the legitimate one.
