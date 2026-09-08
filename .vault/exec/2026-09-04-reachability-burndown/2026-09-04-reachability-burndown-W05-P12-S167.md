---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:17249b688c2807284602c0d33461cc46a7d03b1d772672ca1b64ad49bad8bb50'
step_id: 'S167'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the production Ledger CLI architectural-adjudication census, including its transport-only, mixed, and policy-bearing status vocabulary, per-command annotation ledger, derived census projection, exports, and identity-pinning tests, while retaining the executable LEDGER_COMMAND_SPECS authority and the accepted ADR's shape-based adapter boundary.

## Scope

- `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`
- `src/cadrumo/entrypoints/cli/tests/test_command_specs.py`
- `reachability burndown reference`
- `focused command-spec gates`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_command_specs.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `rg -n "LedgerCliAdapterOwnership|LedgerCliCensusAnnotation|LedgerCliCommandCensusEntry|LEDGER_CLI_COMMAND_CENSUS|_LEDGER_CLI_CENSUS_ANNOTATIONS|_build_ledger_cli_command_census|transport-only|policy-bearing" src/cadrumo -g "*.py"` -> `pass` (no census symbols or status values remain; unrelated prose matches only)
- `verify:` `uv run ruff check src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/entrypoints/cli/tests/test_command_specs.py src/cadrumo/entrypoints/cli/tests/test_ledger_rule_ratio_command_specs.py` -> `pass` (7 passed)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (365 exact symbols, down from 366, and 18 orphaned test modules unchanged)

## Notes

The accepted adapter-migration ADR requires the adapter boundary to be defined and detected positively by behavior shape and explicitly calls its inventory evidence rather than specification. The removed production census contradicted that implementation boundary; no ADR amendment was required.
