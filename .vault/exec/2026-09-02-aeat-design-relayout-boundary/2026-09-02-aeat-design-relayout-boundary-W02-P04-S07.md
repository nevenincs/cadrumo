---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8901d92f14e3ecaf19812c554978bef64c03e70d947981df1b111359e121dd24'
step_id: 'S07'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---
# Implement target-anchor identity classification and explicit dispositions for every unmapped declaration

## Scope

- `dev/registry/analysis/m200_semantic_casilla_candidates.py`

## Changes

- `M` `dev/registry/analysis/m200_semantic_casilla_candidates.py`
- `verify:` `uv run pytest dev/registry/tests/test_m200_semantic_casilla_candidates.py -q -n0` -> `pass`
- `verify:` `uv run ruff check dev/registry/analysis/m200_semantic_casilla_candidates.py` -> `pass`
