---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:371d8d860a14a963d6ee464cd6a9ab08e758b4759f540ba9120e837a2d2744ac'
step_id: 'S14'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---
# Reconcile discovered import preparation into the G0 denominator

## Status

- **Open.** `W01.P04.S14` remains unchecked: this reconciliation changes the reviewed denominator, so the historical independent attestation, G0 closure receipt, and external acceptance anchor are invalid and cannot be reused.

## Reconciliation

- Added `backend_operation:ledger.import.prepare` for `cadrumo.application.ledger.import_preparation:prepare_ledger_import_command`.
- The semantic row is a planned typed `QUERY` (`LedgerImportPreparationRequest` to `LedgerSourceImportCommand`), with `PRODUCT` and `PROOF` gaps. It prepares a validated path and auto-provider command; it does not execute an import.
- Included `src/cadrumo/application/ledger/import_preparation.py` in the backend census source set and made omission of either source or public operation fail closed.
- The installed read-only Overview supported-surface observation now selects `ledger.workspace.read` and `ledger.import.prepare`; it does not select `ledger.import.source`.
- Live union: **761 observations / 771 selected edges / 694 reviewed rows**; union digest `sha256:1abe7593edafc15bf1006ac1ab5926936cebf8e379f1bb268f513de64b7121e8`.

## Evidence

- `src/cadrumo/application/ledger/tests/test_import_preparation.py` directly proves trimming, expansion, existence, file, readability refusals, and command construction without importing the TUI.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/application/ledger/tests/test_import_preparation.py` -> `7 passed`.
- Focused matrix reconciliation lane -> `9 passed`.

## Publication hold

The reference now records G0 as open and labels the old acceptance material historical. Fresh independent review, receipt, and external anchor work is required before this Step can close. The busy TUI-owned paths were not modified or quarantined.
