---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S125'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S125 Justificante Fixture Generator Split

Scope: decompose the oversized justificante fixture generator by fixture family and generation concern.

## Description

- Extracted base fixture records, shared receipt rendering, constants, and sidecar writing into `_generate_base.py`.
- Extracted non-IVA modelo fixture families into `_generate_misc_a.py` and `_generate_misc_b.py`.
- Extracted IVA and pagos-fraccionados corpus fixtures into `_generate_iva_corpus.py`.
- Kept `_generate.py` as the regeneration command entrypoint and compatibility re-export surface for existing tests.

## Outcome

The fixture generator is split into focused modules below the hard size budget while preserving the committed-fixture regeneration entrypoint.

## Notes

Focused generator lint passed, generator smoke tests passed with 2 tests, and the public import smoke passed.
