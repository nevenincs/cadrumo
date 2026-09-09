---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:65b0d246fb744ebfc7061091a8103294654b84e20e9e4cc84396d1cbd0be8a59'
step_id: 'S365'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unconsumed rich-progress terminal policy helper and its stale module contract.

## Scope

- `CLI TTY helper`
- `CLI TTY behavior tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_tty.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_tty.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/entrypoints/cli/tests/test_tty_error_locale.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
