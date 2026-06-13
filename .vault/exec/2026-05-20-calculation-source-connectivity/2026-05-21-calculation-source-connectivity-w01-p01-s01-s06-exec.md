---
tags: ["#exec", "#calculation-source-connectivity"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S01-S06'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-05-21-calculation-source-connectivity-reference]]'
---

# `calculation-source-connectivity` `W01.P01.S01-S06`

Implemented the source mesh contract foundation.

- Created: `src/aeat/application/aggregation/_source_mesh.py`
- Created: `src/aeat/application/aggregation/test_source_mesh.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `.vault/plan/2026-05-20-calculation-source-connectivity-plan.md`
- Created: `.vault/reference/2026-05-21-calculation-source-connectivity-reference.md`

## Description

Added strict frozen source mesh boundary records for source context,
diagnostics, provenance, and source resolution. Added the `ModeloSourceResolver`
application protocol, merge semantics for resolver outputs, duplicate binding
and bound-casilla ownership rejection, and unhandled source diagnostics over a
registry revision's binding declarations.

Exported the new contracts from `aeat.application.aggregation`.

## Tests

`uv run ruff check src/aeat/application/aggregation/_source_mesh.py
src/aeat/application/aggregation/__init__.py
src/aeat/application/aggregation/test_source_mesh.py` passed.

`uv run pytest src/aeat/application/aggregation/test_source_mesh.py -q
--tb=short` passed with 5 tests.
