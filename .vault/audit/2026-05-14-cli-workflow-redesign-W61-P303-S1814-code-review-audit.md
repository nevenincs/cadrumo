---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-per-modelo-aggregation-pipeline-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p303-s1814-exec]]'
---



# `cli-workflow-redesign` W61.P303.S1814 Code Review

No CRITICAL issues were found. HIGH issues are present, so status is REVISION REQUIRED before this step should be treated as audit-clean.

W61.P303.S1814-001 | HIGH | Dated VAT registry gaps crash IVA aggregation instead of producing structured row issues
`aggregate_iva_ledger_observations` promises structured exclusion reasons for unsupported IVA rates, and `IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE` exists for that path. The projection calls `_iva_rate_slot_for` at `src/aeat/application/aggregation/_iva_ledger.py:177` before the `try` block that converts invalid observations into `INVALID_IVA_OBSERVATION` issues. `_iva_rate_slot_for` then calls `iva_rate_percentage` inside its slot loop at `src/aeat/application/aggregation/_iva_ledger.py:244` through `src/aeat/application/aggregation/_iva_ledger.py:247`. If the centralized VAT registry has no dated rate for one checked slot, `iva_rate_percentage` raises `VatRateNotFoundError`; this is not caught and aborts the whole aggregation instead of recording `UNSUPPORTED_IVA_RATE` for the affected row. This is not theoretical: the period model accepts years back to 1990, while the Spanish VAT rate registry starts at 2024. A `2023Q2` ledger row with `iva_rate=Decimal("0.21")` will fail while checking the dated reduced-rate slot before it can reach the 21 percent slot or append a structured issue. This violates the backend no-crash expectation and the S1814 residual/error-reporting contract for unsupported rows.

W61.P303.S1814-002 | MEDIUM | Ledger IVA projection is newly coupled to the pre-taxonomy invoice helper surface
The invoice-domain decoupling ADR forbids generic invoice semantics for ledger movement facts and calls out `domain/invoices/` as a pre-taxonomy package that must be split into source-kind-specific boundaries. The new projector imports `InvoiceKind`, `IvaRate`, `invoice_line_to_iva_observation`, and `iva_rate_percentage` from `aeat.domain.invoices` at `src/aeat/application/aggregation/_iva_ledger.py:13`, passes a ledger transaction id through the helper's `invoice_id` parameter at `src/aeat/application/aggregation/_iva_ledger.py:189` through `src/aeat/application/aggregation/_iva_ledger.py:193`, and expands the invoice public surface with `iva_rate_percentage` at `src/aeat/domain/invoices/__init__.py:10` and `src/aeat/domain/invoices/__init__.py:54`. Runtime output still uses `ledger_id` and no bare `invoice` source kind is emitted, so this is not a correctness failure today. It is still architectural drift: a new ledger-transaction aggregation path now depends on invoice-named APIs instead of a VAT or ledger-owned standard-IVA projector, making the later source-kind split harder and keeping invoice terminology in fresh backend code.

W61.P303.S1814-003 | LOW | Focused tests miss the main unsupported-path and repository-backed success cases
The tests are real-behavior tests and cover outgoing/incoming direction mapping, mixed `business_pct` proportionality, personal exclusion, missing IVA rate, non-canonical rate, period/currency filtering, bucket-mismatch rejection, and a real Modelo 303 binding resolver path. They do not cover a successful `aggregate_iva_ledger_observations_from_repositories` load/save path, `INTERNAL_TRANSFER` producing `UNSUPPORTED_DIRECTION`, all three missing tax-fact issue reasons, zero/super-reduced rate mapping, or the dated VAT registry miss described in `W61.P303.S1814-001`. The parent verification passed 48 focused tests plus ruff and ty on touched files, but the current suite would not catch the crash path or several declared issue-reason branches.

Review notes:

- Bucket isolation is correct for the repository entrypoint's injected-repository mismatch check: `src/aeat/application/aggregation/_iva_ledger.py:96` through `src/aeat/application/aggregation/_iva_ledger.py:102` rejects mismatched repositories before loading.
- Duplicate and shadow handling is not newly weakened by this step. The projector consumes `TransactionCatalogue.values()`, and catalogue construction enforces unique transaction ids and matching mapping keys in `src/aeat/domain/transactions/_models.py`.
- No conflation of `business_pct` with legal IVA prorrata was found. `business_pct` is used only to scale taxable base and IVA amount for `BusinessClassification.MIXED` rows at `src/aeat/application/aggregation/_iva_ledger.py:217` through `src/aeat/application/aggregation/_iva_ledger.py:222`; no prorrata reference or VAT prorrata substrate is read or synthesized.
- The implementation is backend-only and Pydantic-based; no CLI shim, legacy `financial` surface, or operator-local business logic was introduced in the reviewed files.

## Focused remediation re-review 2026-05-14

Status: ACCEPTED for the reviewed S1814 remediation scope. No CRITICAL or HIGH issues remain in the reviewed files.

W61.P303.S1814-001 | RESOLVED | Dated VAT registry gaps no longer crash IVA aggregation
`aggregate_iva_ledger_observations` now resolves rate kinds through `lookup_rate` in `_iva_rate_kind_for` and catches `VatRateNotFoundError` per candidate `VATRateKind`. If no dated registry rate matches, the row produces `UNSUPPORTED_IVA_RATE` instead of aborting aggregation. `test_dated_vat_registry_gap_is_reported_as_unsupported_rate` covers the original 2023 registry-gap scenario.

W61.P303.S1814-002 | RESOLVED | Ledger IVA projection is no longer coupled to invoice helper APIs
The ledger projector imports VAT substrate types from `aeat.domain.vat` and transaction types from `aeat.domain.transactions`; it no longer imports or calls `InvoiceKind`, `IvaRate`, `invoice_line_to_iva_observation`, `iva_rate_percentage`, or `aeat.domain.invoices`. The invoice public surface also no longer exports `iva_rate_percentage` for this path.

W61.P303.S1814-003 | REDUCED | Focused tests now cover the previously missing remediation-critical paths
The test surface now includes repository-backed load/save projection, internal-transfer unsupported direction, missing taxable base, missing IVA amount, the dated VAT registry gap, and zero/super-reduced canonical rate projection. Existing tests still cover outgoing/incoming mapping, mixed business proportionality, personal exclusion, missing IVA rate, non-canonical IVA rate, period/currency filtering, bucket mismatch rejection, and Modelo 303 binding resolution. Residual low-level coverage gap: `UNCLASSIFIED_BUSINESS_STATE` is still not directly asserted in `test_iva_ledger.py`, but this is not blocking for the remediated HIGH finding.

Re-run verification:

- `uv run --no-sync ruff check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/domain/invoices/__init__.py` passed.
- `uv run --no-sync ty check src/aeat/application/aggregation/_iva_ledger.py src/aeat/application/aggregation/test_iva_ledger.py src/aeat/application/aggregation/__init__.py src/aeat/domain/invoices/__init__.py` passed.
- `uv run --no-sync pytest src/aeat/application/aggregation/test_iva_ledger.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py src/aeat/domain/invoices/test_iva_classification.py -q` passed with 53 tests.
