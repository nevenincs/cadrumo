---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:d6b07d60e2521c872779ac78229766db35913af29e6c60bde4276c9337acbd61'
step_id: 'S347'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
