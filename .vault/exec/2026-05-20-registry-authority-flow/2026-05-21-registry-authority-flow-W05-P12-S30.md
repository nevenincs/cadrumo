---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S30'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P12.S30`

Brought the slow registry chunk under the performance budget.

- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_relation_closure.py`
- Modified: this execution record

## Description

Added cached real-registry helpers to the remaining slow chunk files that were
reloading the bundled registry repeatedly inside the same module. The tests
still exercise the committed registry and validator; the change only removes
duplicate load orchestration.

## Tests

`uv run pytest @chunk -q --tb=short --durations=10` for sorted files 85..89
passed with 168 tests in 129.87s, down from 362.83s.

`uv run ruff check
src/aeat/domain/calculations/registry/test_record_design.py
src/aeat/domain/calculations/registry/test_registry_schema.py
src/aeat/domain/calculations/registry/test_relation_closure.py` passed.
