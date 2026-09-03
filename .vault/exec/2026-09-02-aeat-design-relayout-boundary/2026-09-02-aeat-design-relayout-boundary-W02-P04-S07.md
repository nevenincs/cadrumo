---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:4a484b8c6d12cdbf01a01551b64f294c2fd88a390f148b00c1f018384667b481'
step_id: 'S07'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---
# Implement target-anchor identity classification and explicit dispositions for every unmapped declaration

## Scope

- `dev/registry/analysis/m200_semantic_casilla_candidates.py`

## Changes

- `M` `dev/registry/analysis/m200_semantic_casilla_candidates.py`
- `verify:` `uv run python -m dev.registry.analysis.m200_semantic_casilla_candidates` -> `pass`
- `verify:` `uv run ruff check dev/registry/analysis/m200_semantic_casilla_candidates.py` -> `pass`
