---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-07-17'
body_hash: 'sha256:53d6285239e10560e9178f68b75836746f4f032d709453cd693abca8612b90c3'
step_id: 'S06'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# refactor declaracion conftest.py to eliminate wildcard imports

## Scope

- `src/aeat/adapters/inbound/declaracion/tests/conftest.py`

## Description

- Refactored `declaracion/tests/conftest.py` to eliminate wildcard imports of `_parser_boundary_support` and `_verification_chain_support`.
- Replaced wildcard imports with a clean docstring since the support modules do not export any pytest fixtures.

## Outcome

Standard test collection runs without warnings or namespace collisions.

## Notes
