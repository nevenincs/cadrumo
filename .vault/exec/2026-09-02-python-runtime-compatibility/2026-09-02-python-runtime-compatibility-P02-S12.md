---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:2237c607e61aa20fc44dc51d501047bced45f594930a90ab43681ebff7b639e5'
step_id: 'S12'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Exercise annotation contracts through the workspace-manifest path

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace_manifest.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_workspace_manifest.py -o addopts='' -m 'integration and hex_application' -k 'future_forward or local_models or unresolved_forward' -n 0; uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_workspace_manifest.py` -> `pass`
