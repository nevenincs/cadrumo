---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-06-calculation-truth-registry-modelo-200-application-links-exec]]'
---



# `calculation-truth-registry` Code Review

REVIEW-001 | INFO | No findings

The new Modelo 200 application links are declarative registry data only. They
do not introduce Python-side legal truth, compatibility paths, legacy aliases,
or transient development-state checks.

The behaviour test validates the committed registry surface set through the
snapshot model instead of asserting a migration state.

## Verification

- `uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py -q`
  passed.
- `uv run ruff check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
  passed.
- `uv run ty check src/aeat/domain/calculations/registry/test_modelo_200_registry.py`
  passed.
