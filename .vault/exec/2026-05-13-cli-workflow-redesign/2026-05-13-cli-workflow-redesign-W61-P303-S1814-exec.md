---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P303.S1814'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
---

# `cli-workflow-redesign` `W61.P303.S1814`

Closed plan rows:

- `W61.P303.S1814`

## Description

Implemented and remediated backend-only IVA ledger observation projection for bucket-local `ledger_transaction` facts.

`aggregate_iva_ledger_observations_from_repositories` now loads through a bucket-bound `TransactionCatalogueRepository`, rejects repository bucket mismatches before loading, and delegates to the catalogue-level projector.

`aggregate_iva_ledger_observations` projects eligible transactions into `IvaLedgerObservation` records when rows are inside the requested period, EUR-denominated, IVA-settlement directed, business or mixed classified, and carry `taxable_base`, `iva_amount`, and `iva_rate`.

Direction mapping is explicit: `INCOMING` ledger transactions project to repercutido IVA, and `OUTGOING` ledger transactions project to soportado IVA. Mixed business rows apply `business_pct` to taxable base and IVA amount. This is ledger proportionality only and remains separate from legal IVA prorrata.

Unsupported rows produce structured `IvaLedgerAggregationIssueReason` entries instead of silent drops. Covered issue reasons include outside period, unsupported currency, unsupported direction, unclassified or personal classification, missing tax facts, and unsupported IVA rate.

The aggregation public surface now exports the IVA projection models and functions. The projector resolves canonical Spanish VAT rates through `lookup_rate` and catches `VatRateNotFoundError` per candidate rate kind, so dated registry gaps become `UNSUPPORTED_IVA_RATE` row issues instead of aborting aggregation.

The ledger projector is decoupled from invoice helpers and invoice public exports. Aggregation implementation and tests do not import or call `invoice_line_to_iva_observation`, `iva_rate_percentage`, `InvoiceKind`, `IvaRate`, or `domain.invoices`.

## Modified Paths

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `src/aeat/application/aggregation/__init__.py`
- `src/aeat/application/aggregation/_iva_ledger.py`
- `src/aeat/application/aggregation/test_iva_ledger.py`

## Tests

- `uv run --no-sync ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/domain/invoices/__init__.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/domain/invoices/__init__.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/invoices/test_iva_classification.py -q`
  - 53 passed

Added regression coverage for repository-backed success, internal transfer unsupported direction, missing taxable base, missing IVA amount, dated VAT registry gaps, and zero/super-reduced canonical rate projection. Missing IVA rate coverage already existed.

## Residuals

This step projects transaction-local standard IVA facts into registry observations. It does not implement later routing through `application/modelo`; that remains covered by subsequent `W61.P303` rows.

`business_pct` is applied only as ledger business/private proportionality and must not be interpreted as statutory IVA prorrata.
