---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'W03.P06.S27,W04.P07.S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# Calendar justificante warning hardening

## Scope

Calendar filing state now treats AEAT-observed submission evidence as incomplete until a matching justificante has been verified. This closes the local semantics gap between application "ready to file" records and real-world AEAT submission state.

## Changes

- Added `filing.justificante_unverified` warnings to `build_overview_calendar` when calendar entries or filing events carry `submitted_observed` or `accepted` AEAT evidence without `justificante_verified=true`.
- Kept the remediation command on the approved live filed history surface: `aeat app live filed pull --modelo MODELO --year YEAR`.
- Added locale copy for the warning in `en`, `es`, `ca`, and `hu`.
- Added application tests proving the warning appears for AEAT-observed filings and clears when filed-history evidence verifies the justificante artefact.
- Added a CLI strict-mode regression proving `app overview calendar` refuses the warning without `--allow-incomplete` and exposes the `pull` remediation command in JSON output when incomplete mode is explicitly allowed.

## Verification

- `vaultspec-rag search --timeout 90 "overview calendar justificante verified AEAT filed declaration observation Period"` attempted first and timed out with `http_search_timeout`.
- `python -m ruff check` passed for the touched Python files.
- YAML locale parsing passed for `en.yml`, `es.yml`, `ca.yml`, and `hu.yml`.
- `python -m pytest -m "unit or integration" src/aeat/application/overview/tests/test_calendar.py -q --tb=short`: 70 passed.
- `python -m pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -q --tb=short`: 13 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/live/tests/test_filed_capture_calculation_history.py -q --tb=short`: 34 passed.
- `python -m pytest -m "unit or integration" src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_import_flow.py -q --tb=short`: 57 passed.
- `python -m pytest -m "unit or integration" src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -q --tb=short`: 2 passed.

## Live verification

Live authentication was retried against the isolated live root after the local hardening:

- `config auth status --provider clave_movil` reported the provider configured, authenticated, available, and identity-aligned.
- `config auth login --provider clave_movil --fresh` reached AEAT non-QR Cl@ve and timed out with `verification_code_present=true`, diagnostic `20260612T180957Z`.
- A sequential `config auth login --provider clave_movil` reached AEAT non-QR Cl@ve and timed out with `verification_code_present=true`, diagnostic `20260612T181507Z`.
- `config auth login --provider clave_movil` with `AEAT_CLAVE_PREFER_NON_QR=false` reached the AEAT QR Cl@ve route and timed out with `verification_code_present=true`, diagnostic `20260612T181925Z`.

The live backend reached AEAT, but operator-mediated Cl@ve completion did not finish during the allowed 120 second window. Positive live censo/filed/justificante pulls therefore remain open for this execution record.

## Status

Local calendar enforcement and CLI strict-mode integration are complete for this row. Live evidence rows remain open until an operator-completed Cl@ve session can run `config profile censo pull`, `app live filed list`, and `app live filed pull` sequentially.
