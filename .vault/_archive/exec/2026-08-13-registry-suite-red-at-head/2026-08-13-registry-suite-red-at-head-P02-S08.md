---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5fc094d1988dd9cc724658450a0e32706c9b3080548145b790c26ee98a019762'
step_id: 'S08'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---

# Supply the renta-2024 maternidad profile binding to the registry-layer M100 harnesses from the production derivation authority, never a hand-picked literal

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Add one M100 2024 test-support mapping that derives the empty-descendant
  maternity binding through the public domain authority.
- Replace all 13 inline binding literals across the 11 registry harness modules.
- Add an AST census that prevents the raw binding key from returning outside the
  shared helper.

## Outcome

Every M100 registry harness now obtains the nuisance maternity binding from one
shared 2024-specific helper. The helper calls
`compute_deduccion_maternidad_0611` and converts its integer zero at the strict
registry-scenario boundary to `Decimal`; it does not duplicate maternity
arithmetic or import the application layer.

## Notes

- Eleven M100 modules, the domain maternity authority tests, and the AST census:
  141 passed in 64.29 seconds.
- Ruff, format, and scoped diff checks passed.
- The raw binding key now occurs exactly once in registry tests, inside the
  shared helper.
- Main implementation and census landed concurrently in `bbabb9a26a`; the
  strict Decimal boundary correction landed in `60f615724c`.
