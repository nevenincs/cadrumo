---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ebf1ef2bd7b0404b37d9fb82379b5cd1ded4113339f2ef9232d382063a822438'
step_id: 'S08'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# project declared bindings, typed selectors, aggregation operations, and target casillas

## Scope

- `src/cadrumo/application/registry/source_connectivity.py`

## Description

- Project each validated binding declaration without flattening its typed selector or aggregation.
- Derive target casillas through the registry-owned canonical binding/casilla dual.
- Sort binding records and target ids by canonical identity.

## Outcome

The census exposes every declared binding with its exact typed declaration and deterministic canonical target casillas. The application layer contains no independent binding join or selector parser.

## Notes

Ruff passed. A real Modelo 100 2024 snapshot produced 67 binding records; all selectors remained typed Pydantic models and every target set agreed with the registry-owned forward binding primitive.
