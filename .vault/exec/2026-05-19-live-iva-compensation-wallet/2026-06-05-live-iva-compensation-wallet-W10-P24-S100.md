---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S100'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-05-clave-session-reuse-diagnostics-reference]]'
---


# W10.P24.S100 full-range IVA remote-state acquisition

Scope: Wave W10, Phase P24, Step S100.

## Description

- Change the combined IVA remote-state acquisition so filed-history traversal is executed in per-year slices and then aggregated into one command report.
- Scale the CLI watchdog budget by covered year count, plus auth, wallet, and cleanup budgets.
- Keep the command read-only and fail closed before any AEAT filing, payment, confirmation, represented-taxpayer selection, or write path.

## Outcome

Local implementation is in place. `capture_iva_remote_state` now acquires filed-history evidence by year and aggregates the yearly reports before continuing to wallet/cartera capture. The CLI watchdog budget now scales with the requested year span.

Focused validation passed:

- `uv run --no-sync pytest src/aeat/application/live/test_iva_remote_state_acquisition.py::test_year_chunked_filed_history_reports_aggregate_into_one_command_report src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_command_watchdog_budget_scales_with_year_span src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface::test_remote_state_command_watchdog_reports_typed_timeout -q`
- `uv run --no-sync pytest src/aeat/application/auth/test_operator.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/live/test_iva_remote_state_acquisition.py::test_year_chunked_filed_history_reports_aggregate_into_one_command_report src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface src/aeat/entrypoints/cli/test_live_read_subgroups.py::test_live_auth_preflight_lines_redact_active_profile_identifier -q`
- `uv run --no-sync ruff check` on the touched auth/live application and CLI files.

Live closure later succeeded after S101 refreshed authentication. The full-range read-only command:

- reused the persisted Cl@ve session,
- succeeded for filed-history,
- succeeded for wallet/cartera,
- captured 12 filed-history rows and 12 calculation observations,
- persisted one aggregate acquisition manifest, and
- left no stale auth, capture, Playwright driver, or temp-profile browser process.

Profile-local reload, without live AEAT contact, reported 12 IVA history rows, 8 carry-forward lots, and 2 wallet authority decisions. Private financial values from the reload were not copied into this record.

S100 is closed.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

No private taxpayer amounts or live wallet values were copied into this record. The auth failure is recorded by outcome class and redacted diagnostic shape only.
