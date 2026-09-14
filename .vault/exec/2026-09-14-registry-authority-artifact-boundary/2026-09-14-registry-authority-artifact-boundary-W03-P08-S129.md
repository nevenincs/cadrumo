---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:0705a1c853297ac0a2e653ea71235914dcd5ac8acd794c52426b9e7c34378eff'
step_id: 'S129'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---

# Extend the single installed cohort with profile, fact, model, evidence and CLI/MCP isolation and refusal cases

## Scope

- `dev/packaging/tests/test_installed_oracles.py`

## Changes

- `M` `dev/packaging/tests/test_installed_oracles.py`
- `verify:` `uv run --no-sync ruff check dev/packaging/tests/test_installed_oracles.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/packaging/tests/test_installed_oracles.py` -> `pass`
