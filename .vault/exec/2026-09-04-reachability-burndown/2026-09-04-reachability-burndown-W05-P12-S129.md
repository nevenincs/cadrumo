---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:9090893f36947c04051c7d88da74f57b44aabb32227dc8e7acbec28e4752fefa'
step_id: 'S129'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Retire the shipped source-connectivity census and its runtime closure limb, leaving product workspace closure derived only from executable production authorities and removing the development classification subsystem

## Scope

- `source-connectivity ADR amendment`
- `product registry closure`
- `Modelo workspace`
- `development connectivity tooling`
- `bundled census`
- `and tests`

## Changes

- `M` `.vault/adr/2026-08-22-source-casilla-integration-adr.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `dev/audit/size_budget_baseline.json`
- `M` `dev/registry/analysis/modelo_branch_classification.toml`
- `M` `dev/registry/conformance/authorities.py`
- `M` `dev/registry/conformance/cli.py`
- `M` `dev/registry/conformance/closure.py`
- `M` `dev/registry/conformance/tests/test_closure.py`
- `M` `dev/registry/conformance/tests/test_real_closure_outcomes.py`
- `D` `dev/source_connectivity/__init__.py`
- `D` `dev/source_connectivity/check.py`
- `D` `dev/source_connectivity/cli.py`
- `D` `dev/source_connectivity/discovery.py`
- `D` `dev/source_connectivity/live_proof.py`
- `D` `dev/source_connectivity/source_connectivity_authority.py`
- `D` `dev/source_connectivity/tests/__init__.py`
- `D` `dev/source_connectivity/tests/conftest.py`
- `D` `dev/source_connectivity/tests/test_campaign_close.py`
- `D` `dev/source_connectivity/tests/test_census_completeness.py`
- `D` `dev/source_connectivity/tests/test_check.py`
- `D` `dev/source_connectivity/tests/test_cli.py`
- `D` `dev/source_connectivity/tests/test_command_spec_handler_table_resolution.py`
- `D` `dev/source_connectivity/tests/test_command_spec_policy_declaration.py`
- `D` `dev/source_connectivity/tests/test_discovery.py`
- `D` `dev/source_connectivity/tests/test_discovery_resolves_the_real_tree.py`
- `D` `dev/source_connectivity/tests/test_live_proof.py`
- `D` `dev/source_connectivity/tests/test_m182_deferral.py`
- `D` `dev/source_connectivity/tests/test_m193_deferral.py`
- `D` `dev/source_connectivity/tests/test_m232_deferral.py`
- `D` `dev/source_connectivity/tests/test_m296_deferral.py`
- `D` `dev/source_connectivity/tests/test_m360_deferral.py`
- `D` `dev/source_connectivity/tests/test_source_connectivity_authority.py`
- `D` `dev/source_connectivity/tests/test_source_connectivity_authority_contract.py`
- `M` `dev/tests/test_governance_corpus_isolation.py`
- `M` `pyproject.toml`
- `D` `src/cadrumo/_data/source_connectivity/census.toml`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_projection.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/workspace_producers.py`
- `M` `src/cadrumo/application/registry/closure.py`
- `M` `src/cadrumo/application/registry/closure_capture.py`
- `D` `src/cadrumo/application/registry/source_connectivity.py`
- `D` `src/cadrumo/application/registry/source_connectivity_coverage.py`
- `M` `src/cadrumo/application/registry/tests/test_closure_capture.py`
- `M` `src/cadrumo/application/registry/tests/test_closure_models.py`
- `D` `src/cadrumo/application/registry/tests/test_source_connectivity_coverage.py`
- `D` `src/cadrumo/application/registry/tests/test_source_connectivity_inventory.py`
- `D` `src/cadrumo/core/source_connectivity.py`
- `D` `src/cadrumo/core/tests/test_source_connectivity.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_filing_grade_binding_resolution.py`
- `verify:` `uv run ruff check <S129 Python paths>` -> `pass`
- `verify:` `uv run pytest -q registry closure and Modelo workspace tests` -> `pass`
- `verify:` `rg exact deleted source-connectivity imports and types across src/dev` -> `pass`

## Notes

The live filing-grade route gate reports 21 executable-source gaps (3 tests pass, 1 fails); these are current findings for the calculation-route owner, not classifications. The combined development closure lane has 30 passing tests and four failures in the concurrently changed filing-proof authority: three CLI invocations produce no report and the live proof adapter lacks the new `assess_for` method. No source-connectivity symbol participates in those failures.

Remeasurement: 32 unreachable modules, 381 exact unused symbols, 20 orphaned tests, 262 exact unconsumed exports, and 8 unrendered TUI interfaces.
