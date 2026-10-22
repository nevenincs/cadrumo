---
tags:
  - '#exec'
  - '#ledger-tui-doors'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:97ad369eb825e5a1a529eb3291abfb320e53deddf8eda87c3e7ac362543bf134'
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
