---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:fd5262059c148afa513c4f3b5535523fe515183b0af54d59bbdac0413816db04'
step_id: 'S19'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the zero-to-one share once and retire the nine open-coded bound checks, keeping each caller's own refusal and the exclusive split-child rule intact

## Scope

- `src/cadrumo/core/unit_proportion.py`

## Changes

- `M` `src/cadrumo/application/ledger/models.py`
- `M` `src/cadrumo/application/ledger/ratios.py`
- `M` `src/cadrumo/core/unit_proportion.py`
- `M` `src/cadrumo/domain/renta/_ledger_expenses.py`
- `M` `src/cadrumo/domain/transactions/_llm.py`
- `M` `src/cadrumo/domain/transactions/_model_validation.py`
- `M` `src/cadrumo/domain/usage_ratios/_model.py`
- `M` `src/cadrumo/entrypoints/cli/_diagnostics_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_support.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/transactions src/cadrumo/domain/usage_ratios src/cadrumo/application/ledger/tests` -> `pass`
