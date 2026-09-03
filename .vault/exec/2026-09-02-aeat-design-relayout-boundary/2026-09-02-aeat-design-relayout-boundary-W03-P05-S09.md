---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:bd602cbfd5fc3f0599cacbb51152314820d3eea141916880c606e283ebdfa7a8'
step_id: 'S09'
related:
  - "[[2026-09-02-aeat-design-relayout-boundary-plan]]"
---

# Derive the source-bound legal worklist with applicability-window and unresolved-reference evidence

## Scope

- `dev/registry/analysis/m200_2024_full_reconciliation.py`

## Changes

- `M` `dev/registry/analysis/m200_2024_full_reconciliation.py`
- `M` `dev/registry/tests/test_m200_2024_full_reconciliation.py`
- `verify:` `uv run pytest -n0 dev/registry/tests/test_m200_2024_full_reconciliation.py::test_legal_worklist_measures_the_complete_2024_population_and_exposes_open_authority -q` -> `pass`
