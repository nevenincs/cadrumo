---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S13'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor registry conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/domain/calculations/registry/tests/conftest.py`

## Description

- Refactored `registry/tests/conftest.py` to eliminate wildcard imports of `_referential_integrity_support` and `_registry_schema_support`.
- Declared explicit import for the `_modelo_130_snapshot` fixture.

## Outcome

Verification via local test runs confirms that fixtures are successfully resolved and registry tests execute without error.

## Notes
