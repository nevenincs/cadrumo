---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:45964d09e2f6497d1b9937ec6af340ebcdfec91cfa1c1696a383bd9ba845692f'
step_id: 'S04'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Introduce BindingProviderRegistration as the single enrollment authority, derive selector, validator and route lookups from it, move the import-time route invariants onto it, and register the seven unowned kinds as deferred

## Scope

- `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `src/cadrumo/application/modelo/calculation_route.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `M` `src/cadrumo/application/modelo/calculation_route.py`
- `verify:` `uv run --no-sync ruff check` -> `pass`
- `verify:` `uv run --no-sync ruff format --check` -> `pass`
- `verify:` `uv run --no-sync ty check` -> `pass`
- `verify:` `uv run --no-sync basedpyright` -> `pass`

## Notes

The registry test suite cannot be run through pytest in this checkout: the
autouse conftest fixture decodes the bundled authority artifact, which is stale
relative to the authored tree and fails validation before any test body runs.
The 51 cases in the new test module were executed directly instead and all
pass.

The route-to-registration cross-check could not be exercised by importing
`calculation_route`: an unrelated in-flight edit to `domain/renta/_first_slice_routing.py`
removes a symbol `domain/renta/ledger_expenses.py` still imports, breaking the
application import chain, and past that the same stale artifact blocks. Its two
check functions were executed against the live resolver identities instead, with
four fabricated drift inputs proving refusal.

`application/modelo/workspace_manifest.py` still imports a helper deleted from
`bindings.py` by earlier work in this phase and does not import; it was left
untouched.
