---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:f5481d49e11d0751c431e9f3f0a4407884a50d16b984130e3387395f935f7adf'
step_id: 'S90'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Add a tree-wide relative-import resolver as a standing check, so a repoint that emits the wrong dot depth is caught before it reaches a commit

## Scope

- `src/cadrumo/tests/`

## Changes

- `A` `src/cadrumo/tests/test_relative_imports_resolve.py`
- `verify:` `pytest src/cadrumo/tests/test_relative_imports_resolve.py -n 0` -> `pass`
