---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:733b1ed28d14a2f1158068f9f244d80fbd7dc7e32fadfa109a6aed164cbe2621'
step_id: 'S127'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Switch package resource selection to one descriptor and its database; update archive gates and exclude every runtime authoring source and JSON fallback

## Scope

- `pyproject.toml`

## Changes

- `M` `pyproject.toml`
- `verify:` `uv run --no-sync python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` -> `pass`
