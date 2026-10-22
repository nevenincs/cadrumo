---
tags:
  - '#exec'
  - '#ledger-tui-doors'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:7ebcf596041d7d8d0c7374cdf2a3e996c8fcdbdc0e8eea184fea2a164a40ac7a'
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

## Notes

- `S10` Row cost after the change is about 360 us; the rest sits in the domain Transaction model and shared secure storage, outside this step.
