---
tags:
  - '#exec'
  - '#ledger-tui-doors'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:c4d0261c1d436e6c2be4e073fe4107c7a63787765ac37ef1c89fad4077e9cfe0'
related:
  - "[[2026-10-22-ledger-tui-doors-plan]]"
---

# `ledger-tui-doors` ledger

## Changes

- `S01` `A` `src/cadrumo/entrypoints/tui/ledger/tools.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/workspace_injection.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/routes.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/overview.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/entries.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/review.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/import_flow.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/classification.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/evidence.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `S01` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_tools.py`
- `S01` `A` `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_tools.py`
- `S01` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_workbench.py`
- `S01` `A` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_tools.py`
- `S01` `M` `src/cadrumo/locales/en/common.yml`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/hu/common.yml`
- `S01` `verify:` `pytest ledger + runtime ledger tools (196)` -> `pass`
- `S01` `verify:` `pytest TUI + runtime TUI (2528, one gate fixed then rerun)` -> `pass`
- `S01` `verify:` `ruff check/format` -> `pass`
- `S01` `verify:` `lint-imports` -> `pass`
- `S01` `verify:` `ty on touched files` -> `pass`
- `S01` `by:` `orchestrator`
- `S09` `M` `src/cadrumo/application/ledger/list_query.py`
- `S09` `M` `src/cadrumo/application/ledger/tests/test_list_query.py`
- `S09` `A` `src/cadrumo/entrypoints/tests/test_ledger_list_period_partition.py`
- `S09` `verify:` `test_ledger_list_page_benchmark period page cpu_p95 15.6s to 1.06s (budget 3.0)` -> `pass`
- `S09` `verify:` `list query, operation, partition parity and stale-index fallback tests (31)` -> `pass`
- `S09` `verify:` `ruff, lint-imports, ty on touched files` -> `pass`
- `S09` `by:` `O1`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/transactions.py`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/transaction_row_contracts.py`
- `S10` `M` `src/cadrumo/application/ledger/actions_manual.py`
- `S10` `A` `src/cadrumo/adapters/persistence/profile/tests/test_transaction_row_contracts.py`
- `S10` `A` `src/cadrumo/adapters/persistence/profile/tests/test_transaction_catalogue_listing_identity.py`
- `S10` `verify:` `unfiltered list at 30k: CPU mean 15.4s to 12.0s, load() 13.3s to 10.8s (paired, 9 samples)` -> `pass`
- `S10` `verify:` `profile, ledger and domain transaction tests (4432)` -> `pass`
- `S10` `verify:` `secure storage tests (1896)` -> `pass`
- `S10` `verify:` `old/new timestamp witness oracle (43 cases)` -> `pass`
- `S10` `verify:` `ruff, lint-imports, check-types` -> `pass`
- `S10` `by:` `O2`
- `S05` `A` `src/cadrumo/entrypoints/tui/ledger/invoices_import.py`
- `S05` `A` `src/cadrumo/entrypoints/tui/ledger/invoices_wizard.py`
- `S05` `A` `src/cadrumo/entrypoints/tui/ledger/tests/invoices_fixtures.py`
- `S05` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_invoices_import.py`
- `S05` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_invoices_wizard.py`
- `S05` `A` `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_records.py`
- `S05` `A` `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_invoices.py`
- `S05` `A` `src/cadrumo_runtime/host/tests/frontend/tui/ledger_invoices_runtime_harness.py`
- `S05` `A` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_records.py`
- `S05` `A` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_invoices.py`
- `S05` `A` `dev/tui/harness/ledger_invoices_fixtures.py`
- `S05` `A` `dev/tui/harness/tests/test_ledger_invoices_fixtures.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/ledger/record_views.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/ledger/transaction_views.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_record_views.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/ledger/models.py`
- `S05` `M` `src/cadrumo_runtime/host/frontend/tui/runtime_workbench.py`
- `S05` `verify:` `D4 screen, runtime door and harness tests plus ledger workspace tests (191)` -> `pass`
- `S05` `verify:` `ruff, ty on D4 files; lint-imports` -> `pass`
- `S05` `by:` `D4`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/registers_presentation.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/registers_prorrata.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/registers_capital_goods.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/registers_inventory.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/tests/registers_fixtures.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_registers_prorrata.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_registers_capital_goods.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_registers_inventory.py`
- `S06` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_registers_surfaces.py`
- `S06` `A` `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_registers.py`
- `S06` `A` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_registers.py`
- `S06` `A` `dev/tui/harness/ledger_registers_fixtures.py`
- `S06` `verify:` `D5 screen and runtime door tests (117)` -> `pass`
- `S06` `verify:` `ruff, ty on D5 files; lint-imports` -> `pass`
- `S06` `by:` `D5`
- `S04` `A` `dev/tui/harness/ledger_evidence_files_fixtures.py`
- `S04` `A` `dev/tui/harness/tests/test_ledger_evidence_files_fixtures.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_attachments.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_batch.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_common.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_consent.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_doors.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_queue.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_records.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_review.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_tools.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/evidence_files_write.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/tests/evidence_files_fixtures.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_evidence_files_attachments.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_evidence_files_batch.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_evidence_files_reads.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_evidence_files_records.py`
- `S04` `A` `src/cadrumo/entrypoints/tui/ledger/tests/test_evidence_files_tools.py`
- `S04` `A` `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_evidence_files.py`
- `S04` `A` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_ledger_evidence_files.py`
- `S04` `verify:` `D3 screen, runtime door, harness and seam tests (194)` -> `pass`
- `S04` `verify:` `ruff, ty on D3 files; lint-imports` -> `pass`
- `S04` `by:` `D3`
- `S08` `M` `src/cadrumo_runtime/host/frontend/tui/operations/runtime_profile_session.py`
- `S08` `M` `src/cadrumo_runtime/host/tests/frontend/tui/test_runtime_own_accounts.py`
- `S08` `verify:` `runtime door tests (421)` -> `pass`
- `S08` `verify:` `new off-loop binding test fails against the old code` -> `pass`
- `S08` `by:` `orchestrator`

## Notes

- `S10` Row cost after the change is about 360 us; the rest sits in the domain Transaction model and shared secure storage, outside this step.
- `S05` Invoice and transaction updates carry no baseline on the wire; the door re-reads before writing, leaving a race window. Invoice import has no dry run; the apply is bound to the reviewed file by `source_sha256.` The tools composer entry and locale strings land in the integration commit.
- `S06` The three register list operations have no paging fields; screens hold the register and render one page. The tools composer entry and locale strings land in the integration commit.
- `S04` evidence.query, `attachment_queue` and consent.list take no paging fields; screens hold the result and render one page. Detach takes typed identities because no operation lists an entry's attachments. A whole-repo ruff safe-fix run touched four files outside D3; owners confirmed nothing was lost. The tools composer entry and locale strings land in the integration commit.
- `S08` Gate B1 finding from D2: every runtime door's session binding check made a blocking IPC status read on the event loop.
