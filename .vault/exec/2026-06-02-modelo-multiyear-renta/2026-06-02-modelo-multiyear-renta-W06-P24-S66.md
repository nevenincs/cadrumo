---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S66'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# declare the modelo-714 calculation application-link surface in the registry (vaultspec-high-executor)

## Scope

- `src/aeat/_data/registry/aeat/modelos/714/`

## Description

- Declare the Modelo 714 calculation link in the 2021-y-siguientes registry revision.
- Add relation, binding, dependency-classification, parameter, construct, formula, casilla, completeness, and verification registry entries needed by the art.31 calculation chain.
- Retire the stale verification predicate that expected a manual advisory path after casilla 40 became computed.

## Outcome

- Satisfied by the registry application-link surface for `modelo-714-calculation`.
- Registry validation and Modelo 714 registry tests pass with the new relation-backed calculation surface.
- Verified by `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py`, which passed 24 tests.

## Notes

- The application link is deliberately bounded to the current 2021-2025 source-revision window.
