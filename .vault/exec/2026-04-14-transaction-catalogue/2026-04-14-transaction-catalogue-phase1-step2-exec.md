---
tags:
  - "#exec"
  - "#transaction-catalogue"
date: "2026-04-14"
modified: '2026-04-14'
related:
  - "[[2026-04-14-transaction-catalogue-plan]]"
---

# `transaction-catalogue` `phase-1` `step-2`

Completed the CLI surface, colocated tests, bootstrap refresh, and repo-wide verification for the new transaction catalogue feature.

- Modified: `.vaultspec/providers.json`
- Modified: `uv.lock`
- Created: `src/aeat/entrypoints/cli/financial/txs.py`
- Created: `src/aeat/domain/financial/transactions/test_models.py`
- Created: `src/aeat/domain/financial/transactions/test_catalogue.py`
- Created: `src/aeat/domain/financial/transactions/test_cli.py`

## Description

Extended the existing `aeat financial` subgroup with `txs list`, `txs show`, and `txs classify`, all backed by the configured on-disk catalogue file. Added colocated unit coverage for hash stability, classification validation, immutable-return catalogue operations, JSON round-trip persistence, and CLI smoke behaviour. The branch bootstrap commands refreshed `.vaultspec/providers.json` and `uv.lock` as directed in the handover instructions.

## Tests

Executed `uv run pytest src/aeat/domain/financial/transactions`, then the full local gates: `just lint`, `just typecheck`, `just test`, and `just hooks`. All completed successfully.
