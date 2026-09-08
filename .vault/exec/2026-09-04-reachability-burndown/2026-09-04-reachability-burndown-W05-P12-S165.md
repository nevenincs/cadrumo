---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:7595f000b2449e38aad2826cced1e4812aec077b93b7ab85cf1c08ffe3615120'
step_id: 'S165'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Correct the CLI output-surface inventory by excluding test-package modules from its production domain and distinguishing os.write descriptor transport from file-like operator streams, prove both boundaries with detector-teeth tests, and route the resulting real censal-review output finding through the canonical redacted success funnel.

## Scope

- `src/cadrumo/entrypoints/cli/config/_censo_review_cli.py`
- `src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py`
- `signal-burndown-cadence.md`
- `focused output inventory gate and live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/entrypoints/cli/config/_censo_review_cli.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run ruff check src/cadrumo/entrypoints/cli/config/_censo_review_cli.py src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/entrypoints/cli/tests/test_output_surface_inventory.py` -> `pass` (7 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (367 exact symbols and 18 orphaned test modules, unchanged)

## Notes

The remaining live unused-symbol population is the next campaign input. This step removed no reachability finding; it corrected an output detector that had conflated test helpers and descriptor transport with production stream output, then resolved the surviving real bypass through the existing redacted success funnel.
