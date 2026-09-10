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

- `M` `src/cadrumo/domain/calculations/registry/facts/validation.py`
- `M` `src/cadrumo/domain/calculations/registry/_validate.py`
- `A` `dev/registry/tests/test_migrated_legal_parameter_fact_gate.py`
- `verify:` `uv run ruff check src/cadrumo/domain/calculations/registry/facts/validation.py src/cadrumo/domain/calculations/registry/_validate.py dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` -> `pass`
- `verify:` `uv run pytest --confcutdir=dev/registry/tests dev/registry/tests/test_migrated_legal_parameter_fact_gate.py` -> `pass`

## Notes

The ordinary combined pytest collection remains blocked by the concurrent compiler-relocation deletion of `registry._source_evidence_fingerprint` while `registry._validate` still imports it. The isolated dev-registry collection exercises the real canonical compiler and resolver without that unrelated fixture import.
