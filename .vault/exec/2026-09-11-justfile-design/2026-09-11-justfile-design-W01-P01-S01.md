---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:9fb74add902039a9d2b3bfcca93234d0fe0827b53149b21ccd4c0f1d1ea7c3ea'
step_id: 'S01'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Consolidate fresh-worktree planning and initialization behind the canonical setup facade

## Scope

- `dev/init`

## Changes

- `M` `dev/init/__init__.py`
- `M` `dev/init/README.md`
- `M` `dev/init/__main__.py`
- `M` `dev/init/contract.py`
- `M` `dev/init/dotenv.py`
- `M` `dev/init/hooks.py`
- `M` `dev/init/plan.py`
- `verify:` `uv run --no-sync python -m compileall -q dev/env dev/init dev/quality dev/audit` -> `pass`
