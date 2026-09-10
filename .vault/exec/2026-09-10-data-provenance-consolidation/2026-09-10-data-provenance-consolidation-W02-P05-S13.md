---
tags:
  - '#exec'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:95d6bfc4d51058e5078a3e90e11cefbfb52b4d6ae30747ffdee1d58807cea107'
step_id: 'S13'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# Extract shared generic sidecar hash, schema, locality, and digest validation into the sidecar owner

## Scope

- `dev/docs/preprocess/sidecar.py`

## Changes

- `M` `dev/docs/preprocess/sidecar.py`
- `verify:` `uv run pytest dev/docs/preprocess/tests/test_sidecar_contract.py -q` -> `pass`
