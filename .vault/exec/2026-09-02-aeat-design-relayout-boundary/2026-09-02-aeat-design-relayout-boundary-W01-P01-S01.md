---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:e979ccf0779b953d04916bece83cc735570a088b92d37e921ff5cecaed3a9936'
step_id: 'S01'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---
# Extend the deterministic census across 3,173 current declarations, 156 reconstructed candidates, 3,171 exact map-owned rebinds, 2 unmapped declarations, 15 printed-identity diagnostics, 185 map-owner mismatches, and declaration and map legal gaps

## Scope

- `dev/registry/analysis/m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `verify:` `uv run --no-sync python -m dev.registry.analysis.m200_2024_full_reconciliation` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/analysis/m200_2024_full_reconciliation.py dev/registry/tests/test_m200_2024_full_reconciliation.py` -> `pass`
