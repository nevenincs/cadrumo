---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:67eae40e989ef421fced3ef59fd536cfaa9b56d7d93c3d6f0c2faa9266d8646e'
step_id: 'S347'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Replace the CLI command-spec string dependency table with direct validator imports and remove its embedded import probe.

## Scope

- `command-spec kernel`
- `validator reachability`
- `focused command graph tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `M` `src/cadrumo/entrypoints/cli/command_spec.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py src/cadrumo/entrypoints/cli/tests/test_command_graph_consumers.py src/cadrumo/entrypoints/cli/tests/test_command_spec_deferred_targets.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py -k "not handler_target_modules_do_not_import_the_cli_package_facade"` -> `pass`
- `verify:` `uv run --no-sync aeat --help` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/command_spec.py src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The pre-existing `test_handler_target_modules_do_not_import_the_cli_package_facade` source-policy check remains red on `cadrumo.entrypoints.cli._modelo_discovery_cli`; it is outside this validator-reachability change and was not allowlisted or absorbed.
