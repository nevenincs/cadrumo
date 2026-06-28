---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P303.S1817'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p303-s1817-code-review-audit]]"
---

# `cli-workflow-redesign` `W61.P303.S1817`

Closed plan rows:

- `W61.P303.S1817`

## Description

Implemented backend ledger tax-readiness preflight for bucket-local `ledger_transaction` facts and remediated the S1817 review finding.

`preflight_ledger_tax_readiness` uses strict Pydantic report models, loads a bucket-local `TransactionCatalogueRepository`, and rejects repository bucket mismatches before loading transaction rows.

`preflight_transaction_catalogue` filters rows by period, sorts transactions, counts in-period checked rows, and reports readiness issues without mutating catalogue data. It reports missing business classification, missing category, missing taxable base, missing IVA amount, missing IVA rate, missing mixed-use proportionality reference, and unsupported currency.

Preflight evaluates IVA-settlement direction before business classification readiness. Non-IVA settlement directions, including `INTERNAL_TRANSFER`, do not produce readiness blockers for classification, category, tax facts, or proportionality. IVA aggregation continues to trace unsupported directions as aggregation issues.

Mixed rows require `usage_ratio_id` as the business/private proportionality reference. `business_pct` and usage ratio remain ledger business/private proportionality, not legal IVA prorrata. Legal IVA prorrata remains under `domain/vat` and is represented separately in aggregation through `ProrrataLedgerReference`.

Missing IVA fact reasons are delegated from aggregation through `iva_ledger_missing_fact_reasons`. IVA aggregation keeps legal prorrata references separate from IVA ledger observations and issues.

Terminology remains explicit: `ledger_transaction` names movement facts, `purchase_invoice_evidence` names deductible expense evidence only, and `payable_invoice` plus `collectible_invoice` remain business-operation objects.

Public package exports now include the ledger preflight and IVA helper symbols. The S1817 audit records the prior MEDIUM finding as resolved, with no HIGH or CRITICAL issues remaining.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P303-S1817-code-review-audit.md`
- `src/aeat/application/ledger/_preflight.py`
- `src/aeat/application/ledger/__init__.py`
- `src/aeat/application/ledger/test_preflight.py`
- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/aggregation/__init__.py`

## Tests

- `uv run --no-sync ruff check src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_preflight.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger/_preflight.py src/aeat/application/ledger/__init__.py src/aeat/application/ledger/test_preflight.py src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/application/aggregation/test_iva_ledger.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_preflight.py src/aeat/application/ledger/test_actions.py src/aeat/application/aggregation/test_iva_ledger.py -q`
  - 38 passed

Coverage includes bucket-mismatch rejection, period filtering, sorted preflight rows, in-period checked-row counts, non-mutating issue reporting, missing category and tax-fact reasons, mixed-row `usage_ratio_id` readiness, unsupported currency reporting, and ignored internal-transfer readiness rows.
