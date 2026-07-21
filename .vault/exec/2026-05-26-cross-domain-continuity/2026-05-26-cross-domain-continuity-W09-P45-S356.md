---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S356'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-TOMAS-HIGH ledger view does not show iva_category for entries

## Scope

- `operator cannot confirm domestic_exempt classification visually`
- `auditor cannot verify all artistic invoices are marked exempt vs zero by mistake`
- `add iva_category column to ledger view and ledger list output (operator-visible via tr() locale label)`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Ground the ledger view/list IVA category path with `vaultspec-rag` and targeted symbol reads.
- Render the human `ledger list` header with `cli.ledger.labels.iva_category` and emit the persisted `iva_category` value in each row.
- Extend the real CLI UX regression so a classified transaction is visible in both `ledger view` and `ledger list`.

## Outcome

Human `aeat app ledger list` output now includes an operator-visible IVA category column while preserving the existing JSON row payload shape. `ledger view` already rendered `cli.ledger.labels.iva_category`, so no locale edits were required.

## Notes

- Validation: `uv run --no-sync pytest src\aeat\entrypoints\cli\tests\test_ledger_view_ux.py -m integration`.
- Validation: `uv run --no-sync ruff check src\aeat\entrypoints\cli\_ledger_list.py src\aeat\entrypoints\cli\tests\test_ledger_view_ux.py`.
- Initial pytest invocations without `-m integration` selected zero tests because the project default marker is `unit`.
