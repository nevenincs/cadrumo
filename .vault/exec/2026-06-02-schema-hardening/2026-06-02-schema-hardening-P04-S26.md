---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S26'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Audit oversized registry test module decomposition

## Scope

- `src/aeat/domain/calculations/registry`

## Description

- Inventory registry test module count, total lines, and largest files.
- Identify behavior-family decomposition boundaries for oversized test
  modules.
- Record active peer WIP that blocks direct test edits in this slice.
- Define follow-up split order and verification constraints.

## Outcome

- Completed as an audit-only slice. No test modules were edited because
  active peer WIP exists in registry test files.
- Registry tests currently total 140 modules and 39,487 working-tree
  lines; 20 modules are at or above 500 lines.
- Recommended first decomposition target is `test_loader_directory_mode.py`
  because it directly supports the registry fragmentation campaign and
  has clear behavior clusters.
- Recommended next targets are `test_registry_schema.py`,
  `test_referential_integrity.py`, then modelo-specific files beginning
  with M349 and M100.

## Notes

- No production or test code was edited, so no Python tests were run for
  this audit-only step.
- Vault checks and code-review logging were run before commit.
