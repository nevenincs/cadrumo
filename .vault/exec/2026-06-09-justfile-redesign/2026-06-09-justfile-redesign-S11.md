---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:893d57bfd448c9792be9dfdce34f18f26af56d31502e58eb99b65a3af2722999'
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
