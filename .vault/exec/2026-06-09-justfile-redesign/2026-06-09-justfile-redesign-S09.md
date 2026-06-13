---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S09'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor sql conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/conftest.py`

## Description

- Refactored `sql/tests/conftest.py` to eliminate wildcard import of `_secure_objects_support`.
- Replaced wildcard import with a clean docstring since the support module does not export any pytest fixtures.

## Outcome

Standard test collection runs without warnings or namespace collisions.

## Notes
