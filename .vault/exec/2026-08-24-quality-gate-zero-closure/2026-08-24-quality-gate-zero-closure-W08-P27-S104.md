---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:625bf644d15a643d471d3b2633f8bd315b8b6ac57a6d37e52d77625d86b9ddee'
step_id: 'S104'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# Install mutmut as a declared development dependency and pin it, adding no second mutation engine, and record the exact invocation so a run is reproducible outside CI (Terra xhigh fixes and refactors)

## Scope

- `pyproject.toml`
- `uv.lock`

## Changes

- `M` `pyproject.toml`
- `M` `uv.lock`
- `mutmut:` pinned `3.7.0`; bounded source `dev/quality/tautological_assertion_scan.py`; copied scan roots `src/cadrumo` and `dev`; gate `dev/tests/test_tautological_assertion_gate.py`
- `invoke:` `UV_PROJECT_ENVIRONMENT=/tmp/cadrumo-mutmut-venv uv run --frozen mutmut run "dev.quality.tautological_assertion_scan*"` from the repository root in a POSIX environment (WSL on Windows)
- `verify:` mutmut 3.7.0 configuration resolves the bounded source, `dev/tests` copy, and selected gate -> `pass`
- `verify:` `uv lock --check; uv run --no-sync pytest -q -n 0 dev/tests/test_tautological_assertion_gate.py` -> `pass`
