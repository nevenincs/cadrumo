---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:5c3c0b746c23267587a1015e8a3917273be6c531578e632607f307dac0c69bff'
step_id: 'S79'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Repoint the core-struct anchor map at the portals and transactions modules the earlier retirements made public, which still named the private paths and left the staleness check red

## Scope

- `src/cadrumo/tests/test_docstring_core_struct_links.py`

## Changes

- `M` `src/cadrumo/tests/test_docstring_core_struct_links.py`
- `verify:` `pytest src/cadrumo/tests/test_docstring_core_struct_links.py::test_core_struct_anchors_are_unambiguous` -> `pass`
