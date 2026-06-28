---
tags:
  - '#exec'
  - '#m200-internal-casilla-discipline'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S03'
related:
  - "[[2026-06-03-m200-internal-casilla-discipline-plan]]"
  - "[[2026-06-03-m200-internal-casilla-discipline-adr]]"
---

# Refuse internal_only=true with input_kind != COMPUTED

## Scope

- `src/aeat/domain/calculations/registry/_schema.py`

## Description

Second clause added alongside S02 in the `_validate_input_kind` chain: if `internal_only` is `True` and `input_kind` is not `COMPUTED`, raise `RegistryValidationError`. An internal ceiling that is not formula-derived has no legitimate computation surface (an operator does not type a regulatory ceiling, and a binding does not source it from another modelo).

## Outcome

A MANUAL or BOUND internal-only casilla is refused at load. The validator narrows internal_only=True to formula-derived ceilings only.
