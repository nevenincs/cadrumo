---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-07-17'
body_hash: 'sha256:b193c284cb6a75be0423149e4f8d557bb02f18d0b2fed0eda9cc65c8195f68c2'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `Phase 0B` `relation-observation-resolution`

Added relation resolution from normalized filed-declaration observations.

- Modified: `src/aeat/domain/calculations/registry/_relations.py`
- Modified: `src/aeat/domain/calculations/registry/test_relation_closure.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The relation backend can now take the source requirements derived from a
registry revision, match them against normalized filed-declaration observations,
and resolve the relation values needed by the formula runtime.

The resolver fails hard when a required source filing is missing, duplicated, or
does not contain the declared source output. It does not call AEAT directly and
does not introduce fallback defaults.

## Tests

Focused validation was run with:

- `uv run pytest src/aeat/domain/calculations/registry/test_relation_closure.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_relation_closure.py`
- `uv run ty check src/aeat/domain/calculations/registry/_relations.py src/aeat/domain/calculations/registry/test_relation_closure.py`
