---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S10'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor storage conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/adapters/persistence/storage/tests/conftest.py`

## Description

- Refactored `storage/tests/conftest.py` to eliminate wildcard import of `_runtime_migrated_repositories_support`.
- Declared explicit import for the `_isolated_storage` fixture.

## Outcome

Verification via local test runs confirms that fixtures are successfully resolved and storage persistence tests execute without error.

## Notes
