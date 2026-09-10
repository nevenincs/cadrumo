---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:abebec387d2581520556e0c8390ba4636af43f89c15071419a7b51c644f640f5'
step_id: 'S18'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Remove retired off-host-specific tests while retaining catalog-backed detector teeth

## Scope

- `dev/corpus/tests/test_record_design_support.py`

## Changes

- `M` `dev/corpus/tests/test_record_design_support.py`
- `verify:` `uv run pytest dev/corpus/tests/test_record_design_support.py` -> `pass`

## Notes

- Committed atomically with S16 and S17 because either intermediate revision would be unrunnable.
