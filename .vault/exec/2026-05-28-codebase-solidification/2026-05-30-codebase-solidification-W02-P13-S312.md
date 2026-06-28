---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S312'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P13.S312`

Created `src/aeat/test_cast_rationale_inventory.py` — a real-behavior AST-walk test asserting every production `cast()` call carries a `CAST-RATIONALE-*` marker.

- Created: `src/aeat/test_cast_rationale_inventory.py`

## Description

The test uses `ast.parse` to locate genuine `cast()` / `typing.cast()` call nodes (not string occurrences). For each node it scans backward through adjacent comment/blank lines looking for a `CAST-RATIONALE-` substring. Files named `test_*.py` are excluded; non-production prose occurrences inside string literals are never hit because they are string nodes, not `ast.Call` nodes. Marked `unit` + `domain_core`. Additional rationale markers were added to `_streams.py`, `secure_objects.py`, `_engine.py`, and `_repository_test_suite.py` to clear all violations.

## Tests

`uv run --no-sync pytest src/aeat/test_cast_rationale_inventory.py -xvs` — 1 passed. The test found and validated all production cast sites (9 sites across 7 modules).
