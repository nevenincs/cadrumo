---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# W04.F04 IVA wallet history lots and authority decisions

## Scope

- Follow-up: `W04.F04`
- Goal: expose cross-year IVA compensation carry-forward lots and persisted wallet/local/override authority decisions through the operator CLI.

## Changes

- Added `IvaWalletDecisionRepository.list_decisions()` for latest persisted wallet decisions without requiring a target-period probe.
- Extended `list_iva_compensation_history` to use the existing IVA carry-forward engine and return source-period lots with generated, applied, remaining, age, and expiry-review state.
- Extended the same report with persisted authority decisions and structured authority-source summaries, while preserving taxpayer redaction through `taxpayer_ref`.
- Added `aeat app live iva-wallet history --as-of-year` and rendered carry-forward lots, unallocated applied amount, authority decisions, and authority sources in text output.
- Added real encrypted SQL-backed tests for the application report and CLI output-format tests for lots/authority rows.

## Verification

- `uv run pytest src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_history_output_lines_surface_lots_and_authority_decisions src/aeat/entrypoints/cli/test_registry_cli.py::test_live_iva_wallet_cli_help_names_fail_closed_no_submit_policy -q` completed with 4 passed.
- `uv run ruff check src/aeat/application/calculations/_observations_repository.py src/aeat/application/live/__init__.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_registry_cli.py` passed.
