---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:4cb0943459bd86dfd7ac948c344711d57649190f77fc2ac9947beb5a6ac42ef3'
step_id: 'S47'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Implement the AST-backed fixture census with decorator scope autouse constraint owner and consumer fields

## Scope

- `dev/quality/fixture_census.py`

## Description

- Inventory root, source, development, and packaging Python without importing application modules.
- Record fixture declaration identity, lifecycle constraints, normalized bodies, imports, explicit consumers, dynamic requests, and autouse reach.
- Fail closed when an included source cannot be read or parsed.
- Index fixture-name and topology joins so the campaign census does not repeatedly traverse every test function.

## Outcome

The fixture campaign now has a deterministic AST census for the complete maintained source universe. The current shared-tree snapshot contains 709 real fixture declarations; the apparent 710th textual decorator is documentation text. Imported fixtures exposed through a subtree `conftest.py`, static and dynamic `request.getfixturevalue` usage, and autouse reach remain distinct evidence rather than being collapsed into false zero-consumer claims.

## Notes

Semantic discovery was attempted first, but the local RAG service returned HTTP 500 while degraded, so exact repository and VaultSpec discovery supplied the fallback evidence. The first complete indexed census took 44.006 seconds, down from 92.3 seconds before join indexing. Compilation, Ruff, diff integrity, JSON/API smoke checks, and focused imported-through-conftest assertions passed. A shared-tree file disappearance correctly caused one earlier fail-closed run; the stable sequential rerun passed.
