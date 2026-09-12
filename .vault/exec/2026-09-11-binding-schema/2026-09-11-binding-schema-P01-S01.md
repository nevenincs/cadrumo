---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:0bdc7ccac4123599cfdc479277caa3341755e8046e2fee3403302554773b9d30'
step_id: 'S01'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Define BindingValueContract, BindingApplicability, TerminalOriginExpectation, BindingAuthorship and the closed BindingTemporalSelector union in public defining modules

## Scope

- `src/cadrumo/domain/calculations/registry/binding_value_contract.py`
- `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- `src/cadrumo/domain/calculations/registry/binding_terminal_origin.py`

## Changes

- `A` `src/cadrumo/domain/calculations/registry/binding_value_contract.py`
- `A` `src/cadrumo/domain/calculations/registry/binding_temporal.py`
- `A` `src/cadrumo/domain/calculations/registry/binding_terminal_origin.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_value_contract.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_temporal.py`
- `A` `src/cadrumo/domain/calculations/registry/tests/test_binding_terminal_origin.py`
- `verify:` `uv run ruff check <new files>` -> `pass`
- `verify:` `uv run ruff format --check <new files>` -> `pass`
- `verify:` `uv run ty check <new modules>` -> `pass`
- `verify:` `uv run pyrefly check <new modules>` -> `pass`
- `verify:` `uv run basedpyright <new modules>` -> `pass`
- `verify:` `uv run pytest <new tests> -q` -> `pass`

## Notes

Mypy is not installed in the project environment; the configured checkers (ty,
pyrefly, basedpyright) were run in its place. The repository-wide ruff and
import-boundary gates were already failing on unrelated in-flight work; none of
their findings name the files added here.
