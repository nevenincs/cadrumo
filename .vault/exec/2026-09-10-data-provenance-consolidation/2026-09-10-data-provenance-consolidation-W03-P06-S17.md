---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:bc84a4098cac717c3b25c3b23e79f81e67ebc5093174adc63f03af0d7b23f3d5'
step_id: 'S17'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Remove off-host loading, schema, and special authority routing after catalog parity

## Scope

- `dev/corpus/sync_aeat_record_design_corpus.py`

## Changes

- `M` `dev/corpus/sync_aeat_record_design_corpus.py`
- `verify:` `uv run python dev/corpus/sync_aeat_record_design_corpus.py` -> `pass`

## Notes

- Committed atomically with S16 and S18 because either intermediate revision would be unrunnable.
