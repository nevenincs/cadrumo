---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ac49a9e623c16fd9d708fd0034a49089661e9eda2cc6af0c9ad287deacadd2b5'
step_id: 'S268'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Run focused repair gates and exact reachability remeasurement.

## Scope

- `Remove the test-only repair integrity/list report facade and its facade-only tests while preserving the live diagnostics/quarantine owner.`

## Changes

- `M` `src/cadrumo/application/repair_integrity.py`
- `M` `src/cadrumo/application/tests/test_repair_integrity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/repair_integrity.py src/cadrumo/application/tests/test_repair_integrity.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/tests/test_repair_integrity.py src/cadrumo/application/tests/test_diagnostics.py -k "repair or quarantine or remediation"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Twelve focused live diagnostics, quarantine, and remediation tests pass. Exact unused symbols improved from 277 to 275; 31 unreachable modules and zero orphaned tests remain.
