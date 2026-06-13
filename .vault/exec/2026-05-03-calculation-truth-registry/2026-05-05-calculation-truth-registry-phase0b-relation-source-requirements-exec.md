---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `Phase 0B` `relation-source-requirements`

Added a typed backend surface that derives source filing requirements from
registry relations.

- Modified: `src/aeat/domain/calculations/registry/_relations.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_relation_closure.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The relation layer now exposes `relation_source_requirements`, which reads a
validated modelo revision and returns the source modelo, filing year, source
periods, source output, relation ids, target bindings, dependency role, and
aggregation operation required to resolve cross-model dependencies.

This is registry-derived fetch planning only. It does not call AEAT, does not
write remote state, does not introduce legacy fallback behaviour, and does not
hardcode modelo-specific calculation meaning in Python.

## Tests

Focused validation was run with:

- `uv run pytest src/aeat/domain/calculations/registry/test_relation_closure.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_relation_closure.py src/aeat/domain/calculations/registry/__init__.py`
- `uv run ty check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_relation_closure.py src/aeat/domain/calculations/registry/__init__.py`
