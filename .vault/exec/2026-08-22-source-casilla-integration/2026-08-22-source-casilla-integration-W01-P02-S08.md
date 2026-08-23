---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d6f0a84bbc13f51c734457197c96884a14d126096f13923c5b740fbfc07f7b0b'
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
