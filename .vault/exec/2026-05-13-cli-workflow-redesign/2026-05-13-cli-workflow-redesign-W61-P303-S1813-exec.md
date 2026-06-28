---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P303.S1813'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---

# `cli-workflow-redesign` `W61.P303.S1813`

Closed plan rows:

- `W61.P303.S1813`

## Description

Implemented bucket-local Renta ledger aggregation for manual `ledger_transaction` rows and `purchase_invoice_evidence`.

`aggregate_renta_ledger_expenses_from_repositories` now uses `bucket_id` and rejects transaction repository bucket mismatches. `aggregate_renta_ledger_expenses` now receives an explicit `bucket_id`.

Renta aggregation now reads bucket-local transaction facts, including business classification, business pct, category, taxable base, and IVA amount. Manual ledger rows without purchase invoice evidence can feed Renta when transaction tax fields are present.

Purchase evidence enrichment is now named `purchase_invoice_evidence` in issue fields and issue reasons. Evidence bucket mismatch is reported as a structured aggregation issue.

Linked incoming transactions with purchase invoice evidence are treated as refunds and produce negative binding values.

Residuals: current persistence type is still `InvoiceCatalogueRepository` for purchase evidence, and the domain Renta fact still has downstream `invoice_id` naming. `W61.P303.S1814` through `W61.P303.S1818` remain open.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/aggregation/test_renta_ledger.py`

## Tests

- `uv run --no-sync pytest src/aeat/application/aggregation/test_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger_helpers.py src/aeat/application/aggregation/test_renta_ledger_aggregation.py src/aeat/domain/calculations/registry/test_ledger_renta_expense_binding.py -q`
  - 38 passed
- `uv run --no-sync ty check src/aeat/application/aggregation/_renta_ledger.py src/aeat/application/aggregation/test_renta_ledger.py src/aeat/entrypoints/cli/_common.py`
  - All checks passed
