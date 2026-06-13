---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1802'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1802`

Closed plan rows:

- `W61.P301.S1802`

## Description

Ratified the bucket-scoped transaction catalogue repository contract in the W61.P301.S1801 audit document under the new heading "Contract Specification (W61.P301.S1802)". The specification fixes every surface S1803-S1806 must adopt verbatim:

- Module-level constant `TX_BUCKET_NAMESPACE = "aeat.domain.transactions.bucket"` exported from `aeat.domain.transactions`.
- Helper `transaction_catalogue_object_key(bucket_id: str) -> str` returning `f"transaction-catalogue:{bucket_id}"` with non-blank validation.
- Repository constructor `TransactionCatalogueRepository(*, bucket_id: str, objects=...)` with `bucket_id` required and validated. `_TX_NAMESPACE`/`_TX_OBJECT_KEY` are removed by S1803; no parallel paths.
- Read-only `bucket_id` property on the repository for observability assertion sites.
- `ImportSummary.catalogue_path` embeds the bucket id in its URI.
- New workflow helper `active_bucket_id_or_raise(state)` on `aeat.application.workflow`, raising a typed error when no profile is active.
- Application-layer helpers (`aggregate_renta_ledger_expenses_from_repositories`, overview build, invoice reconciliation/linking/queries, review adapters, filing review cache and read) take `bucket_id: str` as a required keyword argument.
- `@lru_cache` on the filing-review cache is keyed on `bucket_id`.
- `derive_transaction_id` remains content-derived; uniqueness contract is per-bucket; cross-bucket consumers qualify with `(bucket_id, tx_id)`.

A new audit finding (W61-P301-S1801-F MEDIUM) was added for S1806 to register a typed `LedgerStorageError` subclass distinguishing "no active bucket" from "catalogue empty / corrupted".

S1802 is a contract-definition step that produces no source changes: the contract lives in the audit document so the implementation steps (S1803-S1806) can be reviewed against a single binding specification without parallel paths existing in source.

## Modified Paths

- `.vault/audit/2026-05-13-cli-workflow-redesign-W61-P301-S1801-ledger-storage-ownership-audit.md`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

No source changes; the contract is documentary. S1803-S1806 land the implementation and tests.
