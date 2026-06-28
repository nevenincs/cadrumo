---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S12'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor modelo conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/application/modelo/tests/conftest.py`

## Description

- Refactored `modelo/tests/conftest.py` to eliminate wildcard import of `_file_flow_support`.
- Declared explicit import for the `repos` fixture.

## Outcome

Verification via local test runs confirms that fixtures are successfully resolved and modelo application tests execute without error.

## Notes
