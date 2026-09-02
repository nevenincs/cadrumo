---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e4294c1d0e8a910372cac4dd7e7f49e9b53a6c192a5e982ab9d4ec5e18d40cbd'
step_id: 'S01'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Change the root package floor to >=3.13 and preserve py313 static-analysis targets

## Scope

- `pyproject.toml`

## Changes

- `M` `pyproject.toml`
- `verify:` `uv run --no-sync python -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb')); assert p['project']['requires-python'] == '>=3.13'; assert p['tool']['ruff']['target-version'] == 'py313'"` -> `pass`
