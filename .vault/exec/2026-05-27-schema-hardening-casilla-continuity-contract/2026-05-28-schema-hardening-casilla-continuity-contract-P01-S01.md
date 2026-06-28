---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S01'
related:
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-plan]]'
---



# `schema-hardening` `P01.S01`

Added the first additive schema surface for the generic casilla continuity
contract.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Created: `.vault/audit/2026-05-28-schema-hardening-casilla-continuity-p01-s01-review.md`

## Description

Added `continuidad_id` as an optional casilla continuity key, revision-level
`continuidad_validation` with default advisory mode, and
`casilla_continuidad_evolutions` records for explicit cross-revision evolution
decisions. The schema remains additive: existing registry TOML continues to
load without continuity metadata, and enforcement remains reserved for later
validator plan steps.

The evolution record requires an id, continuity id, source and target
revisions, an evolution kind, and legal/source grounding. Same-revision
evolution pairs are rejected at the schema boundary.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_schema.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_registry_schema.py -q`
