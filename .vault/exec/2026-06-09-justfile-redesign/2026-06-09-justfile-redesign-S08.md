---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S08'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor sede conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/adapters/outbound/aeat/sede/tests/conftest.py`

## Description

- Refactored `sede/tests/conftest.py` to eliminate the wildcard import of `_declarations_support`.
- Declared explicit import for the `_isolate_secure_object_backend` fixture.

## Outcome

Verification via local test runs confirms that fixtures are successfully resolved and outbound sede tests execute without error.

## Notes
