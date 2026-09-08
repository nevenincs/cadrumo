---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:dd29925f3d8fe3eab9fb476a4e091a159b7b379a9362758e5a69d2fe841402c6'
step_id: 'S122'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Delete the hand-maintained reachability classification metastate and every code or gate dependency on it, replacing exception-driven checks with live structural signals so production source and quality gates remain development-state agnostic

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `.github/workflows/ci.yml`
- `M` `.vault/adr/2026-08-24-tui-modelo-workspace-interface-adr.md`
- `M` `.vault/adr/2026-09-04-reachability-burndown-adr.md`
- `D` `dev/audit/reachability_classification.toml`
- `D` `dev/audit/tests/test_classification_taxonomy_invariants.py`
- `D` `dev/audit/tests/test_external_constants_are_applied_or_adjudicated.py`
- `D` `dev/audit/tests/test_ledger_citations_resolve.py`
- `D` `dev/audit/tests/test_ledger_measurements_are_dated.py`
- `D` `dev/audit/tests/test_reachability_classification.py`
- `D` `dev/quality/modelo_workspace_action_classification.py`
- `D` `dev/quality/modelo_workspace_action_classification_table.py`
- `D` `dev/quality/modelo_workspace_action_denominator.py`
- `M` `dev/quality/suite.py`
- `D` `dev/quality/tests/test_cited_constants_are_protected.py`
- `D` `dev/quality/tests/test_no_unconsumed_consumer_claim.py`
- `D` `dev/quality/tests/test_orphan_test_records_agree.py`
- `A` `dev/quality/tests/test_tui_render_coverage.py`
- `D` `dev/quality/tests/test_tui_render_coverage_ratchet.py`
- `A` `dev/quality/tui_render_coverage.py`
- `D` `dev/quality/tui_render_coverage_ratchet.py`
- `D` `dev/quality/tui_render_coverage_ratchet.toml`
- `M` `dev/quality/unconsumed_export_ratchet.py`
- `M` `dev/quality/unconsumed_export_ratchet.toml`
- `M` `dev/quality/unused_symbol_ratchet.py`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `D` `dev/tests/test_modelo_workspace_action_denominator.py`
- `M` `dev/tests/test_modelo_workspace_fixed_point.py`
- `M` `dev/tui/_coverage.py`
- `M` `dev/tui/cli.py`
- `M` `dev/tui/tests/test_tui_surface_identity_resolution.py`
- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `M` `justfile`
- `M` `src/cadrumo/domain/calculations/registry/inventory_bindings.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_destination_pairing_is_canonical.py`
- `verify:` `uv run --no-sync pytest -q -n0 dev/tui/tests/test_tui_visual_inventory.py dev/tui/tests/test_tui_surface_identity_resolution.py dev/quality/tests/test_tui_render_coverage.py dev/quality/tests/test_suite_gate_table.py dev/tests/test_every_source_file_parses.py` -> `65 passed, 1 skipped`
- `verify:` `uv run --no-sync ruff check <changed Python paths>` -> `pass`
- `verify:` `just check-tui-render-coverage` -> `expected red: 10 concrete interfaces have no executable fixture surface`

## Notes

The Ledger owning test cannot collect because peer-modified calculation modules currently form a circular import through `application.aggregation` and `application.calculations`. The independent Modelo fixed-point test reaches its assertions but remains red on a peer duplicate `declared_destination_ids` authority in `entrypoints/tui/navigation.py`. Neither failure was absorbed or suppressed.
