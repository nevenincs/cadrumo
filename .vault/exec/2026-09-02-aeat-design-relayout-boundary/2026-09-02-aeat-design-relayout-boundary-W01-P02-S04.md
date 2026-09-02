---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:44c747390e1b125796c623eef08806702facb05a0cf3a59d813ba59bef9638ea'
step_id: 'S04'
related:
  - "[[2026-09-02-modelo-200-semantic-crosswalk-plan]]"
---

# Detect target-description, semantic-role, legal-reference, and source-SHA mutations at the historic-restoration boundary

## Scope

- `dev/registry/tests/test_m200_2024_restoration_candidates.py`

## Changes

- `M` `dev/registry/tests/test_m200_2024_restoration_candidates.py`
- `verify:` `uv run --no-sync pytest -q -n 0 dev/registry/tests/test_m200_2024_restoration_candidates.py` -> `pass`
