---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:353d253a6e429e1878ee5b1b029fe84f40eab0417298adda7ba7a80df64b6bdf'
step_id: 'S11'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Replace basename-only off-host assertion with exact catalog identity alignment fixtures

## Scope

- `dev/corpus/tests/test_record_design_support.py`

## Changes

- `M` `dev/corpus/tests/test_record_design_support.py`
- `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py -q` -> `pass`
