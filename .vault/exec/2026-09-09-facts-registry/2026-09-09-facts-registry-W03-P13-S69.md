---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:cd87fb5bd73a8c0c937351f101fd88e92a541be328fcfcfd23887cc59677029b'
step_id: 'S69'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---


# Enforce and prove legal-parameter fact temporal coverage, date-axis selection, provenance, and refusal outside source-grounded windows

## Scope

- `src/cadrumo/domain/calculations/registry/facts/tests and src/cadrumo/domain/calculations/registry/facts/validation.py`

## Changes

- `M` `dev/registry/compiler/fact_validation.py`
- `M` `dev/registry/compiler/validator.py`
- `A` `dev/registry/tests/test_migrated_legal_parameter_fact_gate.py`
- `verify:` `uv run ruff check dev/registry/compiler/fact_validation.py dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` -> `pass`
- `verify:` `uv run pytest -n 0 --confcutdir=dev/registry/tests dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` -> `pass`

## Notes

The ordinary public `RegistryValidator.validate_registry()` completion remains blocked after catalogue validation by the concurrent relocation's `registry_scope` import of missing `dev.registry.compiler.bindings`. The isolated dev-registry collection exercises the real canonical compiler, resolver, and catalogue-validation branch without bypassing that unrelated downstream import.
