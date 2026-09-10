---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b9c27cc4072e44abcb2a122b190b5e07ed7f3f07f5e2717ff0b6f372a8cdc084'
step_id: 'S12'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Prove catalog-backed sync rejects unclassified files and conflicting acquisition identity

## Scope

- `dev/corpus/tests/test_record_design_support.py`

## Changes

- `M` `dev/corpus/tests/test_record_design_support.py`
- `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
