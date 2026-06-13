---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S17'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-censo-calendar-reconciliation-W05-P05-S15]]'
---

# W03.P05.S17 - pull-only live command tree verification

## Description

- Re-grounded the live CLI command tree after the `core.Period` stringification rollout.
- Amended the current plan row to state that filed and expedientes bulk acquisition must stay under `pull` options only, with no `pull-all` alias.
- Renamed exported CLI callback symbols in `_app_live.py` from `capture` vocabulary to `pull` vocabulary while leaving backend capture service names untouched.
- Extended the command-tree regression so exported live CLI callback names ending in `_cmd` cannot contain `capture`.

## Outcome

The operator-facing live command tree exposes filed and expedientes bulk acquisition through:

- `app live filed pull --from-year ... --to-year ...`
- `app live expedientes pull --from-year ... --to-year ...`

No `app live ... pull-all` or `app live ... capture-all` command is registered. The CLI module export surface now uses `filed_pull_cmd`, `filed_pull_sources_cmd`, `iva_wallet_pull_history_cmd`, and `iva_wallet_pull_remote_state_cmd`.

Live AEAT execution was attempted with `uv run aeat --format json config profile censo pull`, but the command refused before AEAT authentication because `AEAT_SECRET_PASSPHRASE` is unset and this runner is non-interactive. The next live censo proof requires a fresh profile whose NIF/NIE/CIF matches the identity the operator authenticates with.

## Verification

- `uv run vaultspec-rag search --timeout 900 "pull-only live command tree pull-all alias Period justificante calendar filing evidence"` returned the prior Period and pull-only live-censo execution records.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m integration -q` passed with 3 tests.
- `uv run ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 55 tests.
- `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m "integration or not integration" -q` passed with 94 tests.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-12-live-pull-verification-sweep-plan.md` passed.

## Review

Scoped diff review found no behavioral regression: the registered Typer command names were already explicit string literals, so callback renaming does not alter operator commands. The added test checks the exported CLI callback vocabulary only; backend `capture_*` application service names remain allowed because they describe persistence implementation rather than CLI verbs.
