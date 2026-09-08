---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:9e374e566a55ac3cacbea372511194caddf0541059bf7d3b7fcdf6351ca5ca65'
step_id: 'S139'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the declared-unimplemented CLI surface and mounted-family metastate model end to end, so command schemas, mounted families, reconciliation, suggestions, and locale co-landing derive only from live CommandSpec and operator-surface authorities

## Scope

- `CLI verb schemas and public API`
- `operator-surface models and manifest`
- `reconciliation projection`
- `locale tooling`
- `and focused tests`

## Changes

- `M` `src/cadrumo/application/operator_surface/models.py`
- `M` `src/cadrumo/application/operator_surface/manifest.py`
- `M` `src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py`
- `M` `src/cadrumo/entrypoints/cli/_operator_surface_reconciliation.py`
- `M` `src/cadrumo/entrypoints/cli/_verb_input_schema.py`
- `M` `src/cadrumo/entrypoints/cli/command_api.py`
- `M` `src/cadrumo/entrypoints/cli/config_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py`
- `M` `src/cadrumo_harness/mcp/_action_capabilities.py`
- `M` `dev/locales/_colanding.py`
- `M` `dev/locales/cli.py`
- `M` `dev/locales/tests/test_contract.py`
- `M` `dev/locales/tests/test_parity.py`
- `M` `dev/tests/test_suggestion_command_conformance.py`
- `verify:` `uv run ruff check <focused S139 paths>` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo_harness/mcp/tests/test_action_projection.py src/cadrumo/entrypoints/cli/tests/test_command_graph_consumers.py dev/tests/test_suggestion_command_conformance.py` -> `pass`
- `verify:` `uv run pytest -q src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py dev/locales/tests/test_contract.py dev/locales/tests/test_parity.py src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py` -> `fail`

## Notes

The focused operator/locale run passed 66 tests and failed only `test_codebase_to_locale_parity` on peer-owned live catalogue drift in all four locales: `tui.declarations.lifecycle.verification_refused` is missing and `aggregation.source_mesh.errors.ambiguous_source_disposition` is extra. S139's exact forbidden-symbol scan is empty and its changed-path, command-graph, MCP, suggestion, manifest, contract, and payload checks pass.
