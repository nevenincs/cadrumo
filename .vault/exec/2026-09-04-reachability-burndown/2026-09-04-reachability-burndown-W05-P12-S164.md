---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:09a0bd06c8bae027e5a4f7a844bb635e4a417deebaff0ae825d76f0bcb59c939'
step_id: 'S164'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the empty CLI output-inventory module exclusion mechanism so every scanned module is considered directly, preserving the newly exposed output-ownership and scanner-scope findings as live failures.

## Scope

- `CLI output surface inventory`
- `focused output gate`
- `live reachability detector`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py`
- `verify:` `rg -n "_EXCLUDED_MODULES" src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py` -> `pass` (zero matches)
- `verify:` `uv run ruff check src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py` -> `fail` (5 passed, live output-ownership findings preserved)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols and 18 orphaned test modules, unchanged)

## Notes

The output gate reports one unowned censal `typer.echo`, one recovery-handoff `os.write`, and five helper-module pipe writes selected from the tests directory. The empty exclusion removal did not change the selected population; these are existing owning-mechanism and scanner-scope findings left live rather than suppressed.
