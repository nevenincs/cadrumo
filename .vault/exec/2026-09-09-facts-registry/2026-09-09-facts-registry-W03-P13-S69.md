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


# Enforce and prove canonical tax-fact temporal coverage, date-axis selection, provenance, and refusal outside source-grounded windows

## Scope

- `dev/registry/compiler/fact_validation.py and dev/registry/compiler/validator.py and dev/registry/tests/test_migrated_legal_parameter_fact_gate.py`

## Changes

- `M` `dev/registry/compiler/fact_validation.py`
- `M` `dev/registry/compiler/validator.py`
- `A` `dev/registry/tests/test_migrated_legal_parameter_fact_gate.py`
- `verify:` `uv run pytest --confcutdir=dev/registry/tests dev/registry/tests/test_migrated_legal_parameter_fact_gate.py -q` -> `6 passed`
- `verify:` `uv run ruff check dev/registry/compiler/fact_validation.py dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` -> `pass`

## Notes

The public `RegistryValidator.validate_registry(())` entry point rejects a compiled catalogue with a required migrated identity removed. The previously blocked `registry_scope` import was repaired by the concurrent compiler-import relocation checkpoint. Independent re-review cleared the original HIGH wiring finding. S69 remains open until its broader planned validation completes.
