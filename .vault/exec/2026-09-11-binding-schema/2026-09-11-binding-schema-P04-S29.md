---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:a3cf80ed4d14d75a8a39589d63a8c0aa136700e1cb1d8df4652b9821fb646b2b'
step_id: 'S29'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Give the non_calculation applicability member an explicit disposition (informational total, box retired in <edition>, consumed by <consumer>), author it on the 303 criterio-de-caja rows whose casillas left the printed form in 2023 and on any other retired-box informational binding the advisory lists, and make the unreferenced-binding advisory exclude explicitly dispositioned bindings

## Scope

- `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- `dev/registry/compiler/validate_bindings.py`
- `dev/registry/analysis/registry_status.py`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/*/bindings/*.toml`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal.py`
- `M` `dev/registry/compiler/validate_bindings.py`
- `M` `dev/registry/analysis/registry_status.py`
- `A` `dev/registry/compiler/tests/test_binding_non_calculation_disposition.py`
- `A` `dev/registry/analysis/tests/test_registry_status_informational_bindings.py`
- `verify:` `uv run --no-sync pytest dev/registry/compiler/tests/test_binding_non_calculation_disposition.py -n 0` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/analysis/tests/test_registry_status_informational_bindings.py -n 0` -> `pass`
- `verify:` `uv run ruff check` on the six touched files -> `pass`
- `verify:` `uv run ty check` on the six touched files -> `pass`
- `verify:` `uv run basedpyright` on the six touched files -> `pass`

## Notes

No modelo 303 binding row was dispositioned. Casillas 62, 63, 74 and 75 are
absent from the authored `casillas/*.toml` fragments of every revision after
2022, but the compiled revisions inherit them through the predecessor chain, so
all four criterio-de-caja bindings still resolve a `casilla_primary` consumer in
2023, 2024-hasta-08-y-2t, 2024-desde-09-y-3t, 2025 and 2026-y-siguientes and none
of them appears in the unreferenced advisory. Authoring a non-calculation
disposition on them would both assert a false absence of consumer and make
`binding_applies_to_period` refuse the bound casillas. Retiring those casillas
from the later editions is a registry-authoring question outside this Step.

The bundled authority artifact is at format v3 while the loader requires v4, so
the domain test module for the applicability union cannot run under the project
conftest; the union round trip was verified by direct execution against the real
`BindingApplicability` adapter instead.
