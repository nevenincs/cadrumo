---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:762415fdf2ae9d0c679fe7f3f8f18f9095740968c6979bfc5a3a807c62aa4eb5'
step_id: 'S344'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the skip-policy parser and invoice-kind singularity detector, retaining runner-visible outcomes and owner behavior tests.

## Scope

- `skip and xfail policy test`
- `invoice-kind singularity test`
- `test inventory and aggregation behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/tests/test_no_skip_xfail.py`
- `D` `src/cadrumo/tests/test_invoice_kind_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "pytest\\.(skip|xfail)|pytest\\.mark\\.(skip|skipif|xfail)|unittest\\.SkipTest|from pytest import .*\\b(skip|xfail)\\b" src dev -g "*.py"` -> `pass`
- `verify:` `uv run --no-sync pytest -q dev/tests/test_test_inventory.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/aggregation/tests/test_non_arising_category_side_is_refused.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/tests/test_test_inventory.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
