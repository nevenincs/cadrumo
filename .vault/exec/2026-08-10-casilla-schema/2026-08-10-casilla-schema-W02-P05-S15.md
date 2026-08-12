---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:27f9da9dda94836fc8ab47cbe257e815ee4d44cdd8b482ac3c9196877f097122'
step_id: 'S15'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# expose classify_official_boxes as the sole derivation of addressed, binding, and undefined from fixed-width layouts, XML dictionaries, and binding-field generation

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Description

- Add the sole public `classify_official_boxes` registry derivation.
- Derive binding-backed fields before every casilla-keyed export scan.
- Incorporate exact XML dictionary identifiers through the S03 parser.
- Fail closed when required XML dictionary evidence cannot be resolved or parsed.
- Prove real M720, M349, layout-less, and Modelo 100 2024/2025 behavior.

## Outcome

Completed with 23 owned dependency tests and 80 combined integration tests passing. Scoped Ruff, formatting, `ty`, BasedPyright, and diff checks passed. Formal review approved with zero unresolved critical, high, or medium findings.

## Notes

The classifier remains declaration-only. It does not infer producers, values, applicability, completeness, or unsupported filler behavior.
