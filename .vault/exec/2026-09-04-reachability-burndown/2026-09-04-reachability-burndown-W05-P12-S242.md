---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:23a3c586ecb925aed4061fa58ab251b332a8541eb7ba0f21ed124d8c47c538d1'
step_id: 'S242'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unreachable error-module resolve_output_language fallback and export; keep the canonical i18n resolver and preserve logger redaction tests without naming or simulating the dead helper.

## Scope

- `Core error rendering module and registry tests`
- `accepted output-language authority`
- `exact symbol signal`
- `focused error gates`
- `cadence reference`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/core/errors/error_codes.py`
- `M` `src/cadrumo/core/errors/tests/test_registry.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/errors/error_codes.py src/cadrumo/core/errors/tests/test_registry.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s242 src/cadrumo/core/errors/tests/test_registry.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
