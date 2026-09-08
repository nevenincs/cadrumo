---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3727bfdc7f6d15e5dae1f9b3f73ae9f20797f3b941b030b0cefb23b7f326ab80'
step_id: 'S149'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the orphan extension-only financial provider selector and its test-only contract; keep content-aware detect_provider as the sole ingest selection path.

## Scope

- `financial provider detection`
- `provider package documentation`
- `dedicated selector tests`
- `focused unused-symbol and provider gates`

## Changes

- `M` `src/cadrumo/adapters/inbound/financial/providers/detection.py`
- `M` `src/cadrumo/adapters/inbound/financial/providers/__init__.py`
- `M` `src/cadrumo/adapters/inbound/financial/providers/_constants.py`
- `D` `src/cadrumo/adapters/inbound/financial/providers/tests/test_detection.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 src/cadrumo/adapters/inbound/financial/providers/tests` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/adapters/inbound/financial/providers/detection.py src/cadrumo/adapters/inbound/financial/providers/__init__.py src/cadrumo/adapters/inbound/financial/providers/_constants.py` -> `pass`
- `verify:` `rg -n "provider_for_extension" src dev .vault --glob '!*.pyc'` -> `pass`
- `verify:` `uv run python -c "from dev.quality.unused_symbol_coverage import run_gate; ..."` -> `pass` (378 live symbols, 20 orphan tests, selector absent)
