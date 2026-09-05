---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:de3de9c41c0a0286b4cae81d45719d15f7225158ca584fd24c068ff3017baf5f'
step_id: 'S14'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---
# Reconcile discovered import preparation into the G0 denominator

## Status

- **Open.** `W01.P04.S14` remains unchecked: this reconciliation changes the reviewed denominator, so the historical independent attestation, G0 closure receipt, and external acceptance anchor are invalid and cannot be reused.

## Reconciliation

- Added `backend_operation:ledger.import.prepare` for `cadrumo.application.ledger.import_preparation:prepare_ledger_import_command`.
- The semantic row is a planned typed `QUERY` (`LedgerImportPreparationRequest` to `LedgerSourceImportCommand`), with backend `ABSENT`/`UNPROVEN`, CLI/TUI `N/A`, `PRODUCT` primary and `PROOF` secondary gaps. Composition, artifact, provenance, and registry are `N/A`; it has no annotation, TUI route, or hold. It prepares a validated path and auto-provider command; it does not execute an import.
- Included `src/cadrumo/application/ledger/import_preparation.py` in the backend census source set and made omission of either source or public operation fail closed.
- The installed read-only Overview supported-surface observation selects only `ledger.workspace.read`; it does not select preparation, `ledger.import.source`, or any import execution.
- Live union: **761 observations / 770 selected edges / 694 reviewed rows**. Preparation is now one of 14 explicit backend-helper-only rows. The higher-level `ledger.import.source` authority and parity gaps remain unchanged.

## Evidence

- `src/cadrumo/application/ledger/tests/test_import_preparation.py` directly proves trimming, expansion, existence, file, readability refusals, and command construction without importing the TUI.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/application/ledger/tests/test_import_preparation.py` -> `7 passed`.
- Focused matrix reconciliation lane -> `9 passed`.

## Publication hold

The active candidate records `REJECT`, zero accepted closure receipts, no external acceptance anchor, and G0 `OPEN`. Fresh independent review, receipt, and external anchor work is required before this Step can close. The busy TUI-owned paths were not modified or quarantined.

