---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]'
---

# `cli-workflow-redesign` Code Review

W61-P301-REVIEW-001 | RESOLVED | Full error-registry enforcement maps registered codes one-to-one to error subclasses.

The ledger storage classes bind to `FAIL_FINANCIAL_LEDGER_STORAGE` and `REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET`, and `src/aeat/domain/transactions/test_repository.py` asserts those bindings directly. The broader `src/aeat/core/errors/test_registry_enforcement.py` suite now passes, and the registry audit reports `orphan_count 0`, `extra_count 0`, and `duplicate_count 0`.

The cleanup removed stale duplicate registry rows for retired or renamed sanitizer, provider, invoice, LLM, and financial transaction codes; made the Google outbound adapter package importable so its registered error classes are discoverable; and registered the modelo amendment override-casilla refusal class.

W61-P301-REVIEW-002 | INFO | No no-argument transaction catalogue repository constructors remain in the audited source slice.

The review pass searched `src/aeat/domain/transactions`, `src/aeat/application/review`, `src/aeat/application/workflow`, and `src/aeat/entrypoints/cli` for `TransactionCatalogueRepository()` without `bucket_id`. No production matches remain. Review adapters and CLI ledger flows resolve bucket-scoped repositories through explicit `bucket_id` or `active_transaction_catalogue_repository`.

W61-P301-REVIEW-003 | INFO | Legacy root review wording is absent from the audited source slice.

The review pass searched the audited source slice for `aeat review show` and found no remaining production or test references. The stale test expectation found during verification was updated to `aeat app review show`.
