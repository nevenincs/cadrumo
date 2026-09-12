---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:6429182c6d6db536f1671955b07685bea6591252ae0a0e752d387bcd2f597fc9'
step_id: 'S14'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Run registry verify, owning tests and import-boundary gates; record outcomes

## Scope

- `dev/registry/tests/`
- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/application/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_value_contract.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_provider_registration.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_origin.py`
- `A` `dev/registry/fix_binding_row_set_contracts.py`
- `A` `dev/registry/tests/test_fix_binding_row_set_contracts.py`
- `A` `dev/registry/tests/test_binding_registration_corpus_gate.py`
- `M` `dev/registry/convert_binding_provider_shape.py`
- `M` `dev/registry/tests/test_convert_binding_provider_shape.py`
- `M` `justfile`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline publish-authority` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_binding_registration_corpus_gate.py -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_convert_binding_provider_shape.py dev/registry/tests/test_fix_binding_row_set_contracts.py -n 0` -> `pass`
- `verify:` `uv run --no-sync ty check` on the touched modules -> `pass`

## Notes

The corpus rewrite this Step provisioned was already applied by a concurrent
writer: `fix_binding_row_set_contracts --all --dry-run` reports 336 of 336
row-producing rows already on the row-set shape and zero rewrites pending, so
the tool ran as a verified no-op and no registry data file was written. The
before/after hash comparison of all 774 authored binding fragments shows zero
changes.

The registry test suites cannot run under `pytest` in this tree: a session
fixture loads the bundled authority artifact, which is stale against the
current schema (`casilla_continuidad_evolutions` is no longer an enrolled
family) and fails collection for 63 unrelated tests. The domain tests for this
Step were therefore verified by direct execution instead, 93 passing across the
value-contract, registration, and terminal-origin modules.
