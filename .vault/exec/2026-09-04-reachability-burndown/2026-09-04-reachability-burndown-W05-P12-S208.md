---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a4960d5971220bee4b6c54b8c76d88dd22f88f2a8f680da2518e94a873b21e88'
step_id: 'S208'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only clear_runtime_fingerprint_cache facade and its export/documentation from production filing runtime, and make the focused cache test clear the two canonical cache owners directly while retaining the live one-second runtime cache, canonical registry collector cache, and fingerprint behavior.

## Scope

- `Filing runtime and focused cache test`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/filing/runtime.py`
- `M` `src/cadrumo/application/filing/tests/test_runtime.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/runtime.py src/cadrumo/application/filing/tests/test_runtime.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> src/cadrumo/application/filing/tests/test_runtime.py::test_registry_tree_fingerprint_ttl_cache` -> `pass` (1 passed)
- `verify:` `rg -n "clear_runtime_fingerprint_cache" src/cadrumo --glob '*.py'` -> `pass` (no matches)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (319 exact unused symbols; target absent)

## Notes

The exact unused-symbol count fell from 320 immediately before S208 to 319 after removal of the cache-reset facade; the live graph otherwise remained at 65 unreachable modules, 18 orphaned tests, and 2028/2094 shipped modules reachable.
