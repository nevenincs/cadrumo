---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S29'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
  - '[[2026-06-12-live-pull-verification-sweep-code-review-audit]]'
---

# W04.P07.S29 - cross-period taxpayer identity gate

## Description

- Re-grounded the cross-period clean-state gap with `vaultspec-rag search --timeout 900` against taxpayer identity, justificante metadata, AEAT live capture, calendar projection, and Modelo filing evidence.
- Tightened justificante-backed cross-period evidence matching so `AEAT_LIVE_CAPTURE` and `AEAT_JUSTIFICANTE_PDF` cannot clear clean-state when neither `member_nif` nor the active taxpayer identity is known.
- Preserved group-member behavior by continuing to prefer `filing.member_nif` before falling back to the active taxpayer identity.
- Added a regression proving a matching receipt with no expected taxpayer identity is rejected.
- Kept accepted-path tests explicit about the taxpayer axis, so modelo, ejercicio, and typed period agreement alone is not enough to imply AEAT filing state.

## Outcome

The cross-period filing gate now fails closed for non-member justificante-backed evidence when the taxpayer identity axis is absent. A live or parsed receipt can still prove AEAT filing state only when it matches modelo, filing year, typed period, and taxpayer or group-member NIF.

This supports the calendar/modelo distinction that a local app filing record is not equivalent to real-world AEAT filing unless the official AEAT evidence is taxpayer-bound and reconciled.

## Verification

- `uv run vaultspec-rag search --timeout 900 "cross period clean state taxpayer identity justificante AEAT live capture calendar modelo filing verified evidence"` returned the prior HIGH audit for non-member justificante evidence not being taxpayer-bound.
- `uv run ruff check src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py` passed.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py -m "integration or not integration" -q` passed with 31 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py -m "integration or not integration" -q` passed with 129 tests.
- `TMP=Y:\tmp\aeat-pytest TEMP=Y:\tmp\aeat-pytest uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_filed_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_expedientes_pull_cli_help_supports_bulk_options_without_pull_all src/aeat/entrypoints/cli/tests/test_registry_cli.py::test_live_command_tree_rejects_pull_all_and_capture_all_aliases -m "integration or not integration" -q` passed with 3 tests.
- `rg "pull-all|pull_all" src/aeat/entrypoints src/aeat/application src/aeat/locales -n` found only command-tree guard assertions in `test_registry_cli.py`; no active CLI command registration exposes `pull-all`.
- Code review `LPS-010` found no blocking issues.

## Notes

- This record does not close the full W04.P07.S29 row. The row also covers other focused gates, registry filed-state verification, and access gates outside this narrow cross-period taxpayer identity slice.
- Authenticated live AEAT exercise still requires operator login with a live taxpayer identity and a valid profile secret; no live pull was claimed in this local gate.
