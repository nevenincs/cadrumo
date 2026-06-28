---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18,S27,S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W03.P05.S18 / W03.P06.S27 / W04.P07.S29 pull verb and expediente fixture closure

## Scope

Closed the valid-official-fixture breakage found in LPS-043 and recorded the
operator-facing `pull` versus `pull-all` drift watch in the active plan.

## Description

- Bound fixture AEAT justificante CSV and expediente metadata before clean-state
  observation persistence so valid official source observations carry both
  register reference and justificante evidence.
- Updated the Modelo verified-complete regression fixture to retain the same
  expediente reference while satisfying formatting gates.
- Rechecked the production live CLI command tree and help output so bulk filed
  and expedientes acquisition remains exposed only through `pull` options.
- Added an explicit plan tracking update that forbids `pull-all` in production
  commands, help, exec records, and live runbook instructions.

## Outcome

LPS-043 is resolved for the observed red fixture paths. The filed flow and
verified-complete regression now pass with the stronger cross-period clean-state
expediente requirement, and the live command surface remains `pull`-only for
bulk acquisition.

## Verification

- `uv run ruff check src/aeat/application/modelo/tests/_file_flow_support.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`
  - result: passed.
- `uv run pytest src/aeat/application/modelo/tests/test_file_flow_filing.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py -q --tb=short`
  - result: 10 passed.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py -q --tb=short`
  - result: 47 passed.
- `uv run pytest src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q --tb=short`
  - result: 44 passed.
- `rg -n "pull-all|pull_all|pull all|Pull all|pull-all" src/aeat/entrypoints/cli src/aeat/application/live src/aeat/application/overview .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md`
  - result: production matches absent; remaining matches are plan text and
    tests asserting the alias is absent.
- `uv run aeat app live filed --help`
  - result: commands are `list`, `pull`, and `pull-sources`.
- `uv run aeat app live expedientes --help`
  - result: commands are `pull`, `list`, `view`, and `latest`.
- `uv run pytest -m "" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py -q --tb=short`
  - result: 6 passed.
- `uv run pytest -m "" src/aeat/application/overview/tests/test_calendar.py src/aeat/application/overview/tests/test_calendar_filing_evidence.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -q --tb=short`
  - result: 171 passed.
- `uv run ruff check src/aeat/application/overview src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py src/aeat/entrypoints/cli/tests/test_app_live_filed_rendering.py src/aeat/application/calculations/tests/test_cross_period_clean_state_provenance.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/modelo/tests/_file_flow_support.py src/aeat/application/modelo/tests/test_verificado_completo_regression.py src/aeat/application/modelo/tests/test_export.py src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`
  - result: passed.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md`
  - result: passed.

## Notes

The authenticated live runner remains at the operator passphrase prompt. This
record does not claim a new live AEAT read, censo pull, filed-history pull, or
justificante pull.
