---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S11'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor ledger conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/application/ledger/tests/conftest.py`

## Description

- Refactored `ledger/tests/conftest.py` to eliminate wildcard import of `_action_test_support`.
- Declared explicit import for the `secure_objects` fixture.

## Outcome

Verification via local test runs confirms that fixtures are successfully resolved and ledger application tests execute without error.

## Notes
