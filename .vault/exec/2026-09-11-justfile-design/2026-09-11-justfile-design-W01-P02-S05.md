---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:aa4b03e0f01729696c9a00a241192b47ec1d39a5073c77d8658b1f3320760a99'
step_id: 'S05'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Extract one shared persistence write-path analysis core for blocking and diagnostic consumers

## Scope

- `dev/quality/write_path_coverage.py`

## Changes

- `M` `dev/quality/write_path_coverage.py`
- `verify:` `uv run --no-sync python -m dev.quality.write_path_coverage --json` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.write_path_coverage --json` -> `pass`
- `verify:` `uv run --no-sync pytest --confcutdir=dev -n0 -m integration -q dev/tests/test_write_path_coverage_gate.py -k "not live_shipped"` -> `pass`
