---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
---



# `cli-workflow-redesign` Code Review



Status: REVISION REQUIRED

S1828-001 | HIGH | `aeat app ledger remove` and `aeat app ledger reset` mutate bucket data without an explicit confirmation gate
`src/aeat/entrypoints/cli/_ledger.py` exposes `ledger_remove` with only `--dry-run` and then calls `remove_manual_transaction` directly when `--dry-run` is absent. The same pattern exists for `ledger_reset`, which clears the active bucket ledger catalogue without requiring a `--yes`-style confirmation. Existing destructive config surfaces in this codebase gate deletion/reset operations with explicit confirmation, and the S1828 tests in `src/aeat/entrypoints/cli/test_cli_surface.py` currently assert the unsafe path by expecting plain `remove` and plain `reset` to succeed. This is a destructive command safety gap and can cause accidental loss of active-bucket ledger rows.

S1828-002 | HIGH | Ledger export records a durable export event before the CLI output file is written
`export_ledger_transactions` in `src/aeat/application/ledger/_actions.py` saves the `LEDGER_TRANSACTION_EXPORTED` bucket event before returning the payload. `ledger_export` in `src/aeat/entrypoints/cli/_ledger.py` writes `result.payload` to the operator path afterward. If that filesystem write fails, the bucket history still records an export that the CLI did not actually deliver. That breaks the audit meaning of export event history and leaves no rollback path because the event has already been persisted with the transaction catalogue.

S1828-003 | MEDIUM | Backend-owned curated help omits four S1828 lifecycle commands
S1828 exposes `attach`, `remove`, `reset`, `stash`, `archive`, and `export`, but `src/aeat/application/operator_surface/_help.py` lists only `attach` and `export` in the root/app ledger help sections. The command-specific Typer help exists, but the backend-owned operator surface does not advertise `archive`, `stash`, `remove`, or `reset`, so the accepted lifecycle vocabulary is incomplete in the curated help contract that this scope includes.

## Remediation

S1828-001 remediation added explicit `--yes` confirmation gates to `aeat app ledger remove` and `aeat app ledger reset`. Dry-run remains available without confirmation. Real Typer tests now assert plain destructive invocations fail and confirmed invocations succeed.

S1828-002 remediation moved CLI file writing into the application export command path by adding `output_path` to `LedgerExportCommand`. `export_ledger_transactions` writes the output payload before saving the durable export event when an output path is supplied. A service test passes a directory as the output path and verifies the write failure leaves no export event in bucket history.

S1828-003 remediation updated backend-owned curated help to list `archive`, `stash`, `remove`, and `reset` alongside `attach` and `export`.

Final verification after remediation:
- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/operator_surface/_help.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py -q` (`86 passed`)
- `uv run --no-sync python -m aeat.locales audit`

S1828-REREVIEW-001 | INFO | S1828 remediation re-review is clean with one unrelated verification blocker
Re-reviewed only the S1828 remediation scope. `remove` and `reset` now require `--yes` for real mutation while allowing `--dry-run` without confirmation. CLI export passes `output_path` into `export_ledger_transactions`, and the application action writes the output bytes before saving `LEDGER_TRANSACTION_EXPORTED`. Backend-owned help now lists the S1828 lifecycle commands: `attach`, `archive`, `stash`, `remove`, `reset`, and `export`. The remediation tests exercise real Typer/service behavior; the service-level export write-before-event regression test passed independently. Locale audit passed. Residual verification: the focused CLI pytest target could not start because CLI import fails before S1828 execution with `AmendmentVerificationRefusedError` missing an `ErrorCode` registry entry, which is outside this S1828 scope.
