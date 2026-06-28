---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P302.S1809'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W61.P302.S1809`

Closed plan rows:

- `W61.P302.S1809`

## Description

Promoted manual ledger tax and proportionality fields into strict transaction payloads.

`Transaction` now carries aggregation-visible manual ledger fields as first-class data: `business_classification`, `business_pct`, `category_id`, `taxable_base`, `iva_rate`, `iva_amount`, `irpf_category`, `usage_ratio_id`, `prorrata_reference`, `purchase_invoice_evidence_ids`, and `attachment_ids`. Domain validation keeps `business_pct` coupled to `MIXED`, rejects negative tax substrate values, and normalizes evidence and attachment identifier tuples while rejecting blanks and duplicates.

`ManualLedgerTransactionCommand` already carries the same field set, and the manual ledger create/update services now persist those values into the strict `Transaction` payload as well as raw provenance fields.

Renta aggregation now reads transaction-level `taxable_base` and `iva_amount` when no linked invoice payload exists, so manual ledger rows can feed deductible-expense observations without parsing raw provenance or requiring an invoice catalogue.

No CLI command was added in this step.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/aggregation/test_renta_ledger.py`
- `src/aeat/application/ledger/_actions.py`
- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/domain/transactions/_models.py`
- `src/aeat/domain/transactions/test_models.py`

## Tests

- `uv run --no-sync pytest src/aeat/domain/transactions/test_models.py src/aeat/domain/transactions/test_catalogue.py src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/test_renta_ledger.py -q`
