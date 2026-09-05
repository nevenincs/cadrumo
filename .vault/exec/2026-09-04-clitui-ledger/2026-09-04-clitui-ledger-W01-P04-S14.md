---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:2b7d4ccb5ce23381377a3c73d2df82006627c1419a47bd8178b5e6a79ac1a87d'
step_id: 'S14'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---
# Reconcile discovered import preparation into the G0 denominator

## Status

- **Open.** `W01.P04.S14` remains unchecked: this reconciliation changes the reviewed denominator, so the historical independent attestation, G0 closure receipt, and external acceptance anchor are invalid and cannot be reused.

## Changes

- Added `backend_operation:ledger.import.prepare` for `cadrumo.application.ledger.import_preparation:prepare_ledger_import_command`.
- The semantic row is a planned typed `QUERY` (`LedgerImportPreparationRequest` to `LedgerSourceImportCommand`), with backend `ABSENT`/`UNPROVEN`, CLI/TUI `N/A`, `PRODUCT` primary and `PROOF` secondary gaps. Composition, artifact, provenance, and registry are `N/A`; it has no annotation, TUI route, or hold. It prepares a validated path and auto-provider command; it does not execute an import.
- Included `src/cadrumo/application/ledger/import_preparation.py` in the backend census source set and made omission of either source or public operation fail closed.
- The installed read-only Overview supported-surface observation selects only `ledger.workspace.read`; it does not select preparation, `ledger.import.source`, or any import execution.
- The TUI source selector hashes full Ledger package, dedicated Ledger test, and Ledger specification bodies. For the five shared composition roots it hashes only deterministic AST/source facts for Ledger imports, named factories, injected actions, and destination enrollment; unrelated TUI helpers cannot reopen G0, while a Ledger dependency, door, route, or enrollment change does.
- Live union: **761 observations / 770 selected edges / 694 reviewed rows**. Preparation is now one of 14 explicit backend-helper-only rows. The higher-level `ledger.import.source` authority and parity gaps remain unchanged.
- The predecessor TUI plan ownership check is Ledger-scoped: it requires unique Step identities, exact coverage of 27 retained evidence rows, one retired-premise marker, and five displaced-and-held rows, plus retained-checked, retired/held-open, mixed-scope, and `S411` target clauses. It carries no whole-plan row or checked-count pin, so unrelated predecessor-plan edits do not reopen `clitui-ledger`.
- The publication now binds its cohorts to the canonical matrix/TUI projections: 690 planned rows, 148 non-registry rows, 14 backend-helper/TUI-not-applicable rows, and 690 planned rows retaining a `PRODUCT` gap. Production has two read `ActionReference`s plus an inert classification `ActionReference` without target/submitter, and zero executable mutation doors.

## Evidence

- `src/cadrumo/application/ledger/tests/test_import_preparation.py` directly proves trimming, expansion, existence, file, readability refusals, and command construction without importing the TUI.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/application/ledger/tests/test_import_preparation.py` -> `7 passed`.
- `uv run --no-sync pytest -q -n 0 .vaultspec/tests/clitui_ledger` -> `341 passed in 1383.93s`.
- Structural selector and digest tests prove an unrelated shared-root helper change is excluded while Ledger import and dependency changes are included.
- `uv run --no-sync pytest -q -n 0 .vaultspec/tests/clitui_ledger/test_plan_ownership.py` -> `25 passed`.
- Canonical candidate: source `sha256:9bac7ef60ccf03565e4e2391696ceae19ae97859c04a9b500318c4d4b7ed0ca3`; TUI census/source `sha256:f36c5a00d48729e1678a3fa5ecb5204d223d0087395d3919f14f88c3725913cd` / `sha256:29174310f657c3c0f5267d2581d4493fcbb73b2bdd063eb53e255518cbb738b8`; union `sha256:6294c485888e8e01d095789ec317e743d506bb1c5b16044d5cd179f640f5b703`; denominator `sha256:674900e3f784b83b0449f6328d7b3d2094adf87a76d9a9f065ddef4da04885e4`; matrix `sha256:d14aae6c17e1d6e3fb6748c3c67fd9998d7a07fe354d092884140bd458fb5e87`; pre-receipt basis `sha256:293694aec7210c5ee145da1b7a90b7c6579410dc69ef248ba7df4b085e5f29b5`; preacceptance attestation `sha256:d1e3641f5fc8c888ce1e3a2497a2b1362a73e0b5a3862993697be8e5c5837700`.

## Publication hold

The active candidate records `REJECT`, zero accepted closure receipts, no external acceptance anchor, and G0 `OPEN`. Fresh independent review, receipt, and external anchor work is required before this Step can close. The busy TUI-owned paths were not modified or quarantined.
