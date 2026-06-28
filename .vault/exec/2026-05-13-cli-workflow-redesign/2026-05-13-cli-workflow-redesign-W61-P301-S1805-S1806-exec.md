---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1805-S1806'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1805-S1806`

Closed plan rows:

- `W61.P301.S1805`
- `W61.P301.S1806`

## Description

**Migrated ledger import and review projections to bucket-scoped transaction storage (S1805).**

Every production helper that previously fabricated a fallback `TransactionCatalogueRepository()` now takes `bucket_id: str` as a required keyword argument and passes it through:

- `aggregate_renta_ledger_expenses_from_repositories` (`application/aggregation/_renta_ledger.py`)
- `build_overview_status_report` (`application/overview/__init__.py`) — gracefully returns an empty `TransactionCatalogue` when no profile is active so the read-only deadline-calendar view continues to work pre-setup
- `reconcile_invoice_repositories`, `link_invoice_transaction_repositories`, `verify_invoice_repository_links` (`application/invoices/_reconciliation.py`, `_linking.py`, `_queries.py`)
- `transactions_pending`, `transactions_low_confidence`, `ReviewQueue.collect` (`application/review/_adapters.py`, `_aggregator.py`)
- `project_review_queue` (`application/review/_operator.py`) — resolves the active bucket via `active_bucket_id_or_raise(workflow_state_repository().load())` at the boundary
- `compute_current_approval_basis`, `approval_stale_reasons`, `approve_draft`, `refresh_review_status`, `validate_draft` (`application/filing/_review.py`, `application/filing/__init__.py`)
- `_load_transaction_catalogue_cached`, `_read_transaction_catalogue` (`application/filing/_review.py`) — `@lru_cache(maxsize=8)` is now keyed on `bucket_id` so profile switches naturally select different cache entries
- CLI layer (`cli/_common.py`, `cli/_ledger.py`, `cli/_overview.py`): `_tx_repo(state)`, `_load_transactions(state)`, `_aggregate_filing_inputs(modelo, period, state)` thread the active bucket through.

Eight tests migrated to pass an explicit `bucket_id="test"` (or per-fixture id):

- `application/aggregation/test_renta_ledger.py`
- `application/review/test_aggregator.py`
- `application/review/test_adapters.py`
- `application/filing/test_filing.py`
- `application/filing/_testing_registry.py`
- `domain/invoices/test_repository.py`
- `domain/invoices/test_reconciliation.py`
- `entrypoints/cli/test_workflow_surface.py`
- `entrypoints/cli/test_cli_surface.py` — the ledger-import round-trip test now first runs `aeat config init --quiet --tax-id 12345678Z --activity Test` to activate a profile before importing transactions.

**Registered the typed error for "no active profile" (S1806).**

- Added `NoActiveProfileError` to `aeat.application.workflow._errors`, inheriting from `WorkflowError`.
- Registered the canonical error code `REFUSED_NO_ACTIVE_PROFILE` (category `REFUSED`) in `aeat.core.errors.registry._application` with message key `errors.refused.refused_no_active_profile`.
- CLI translates `NoActiveProfileError` to the operator-facing `cli.common.errors.no_active_profile` locale key at the entrypoint boundary (`cli/_common.py:_active_bucket_id_or_bad` and `cli/_common.py:_tx_repo`).
- Application-layer callers (review, filing, modelo) propagate `NoActiveProfileError` unchanged so downstream consumers can distinguish "no active bucket" from "catalogue empty" or "catalogue corrupted".

## Modified Paths

- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/overview/__init__.py`
- `src/aeat/application/invoices/_reconciliation.py`
- `src/aeat/application/invoices/_linking.py`
- `src/aeat/application/invoices/_queries.py`
- `src/aeat/application/review/_adapters.py`
- `src/aeat/application/review/_aggregator.py`
- `src/aeat/application/review/_operator.py`
- `src/aeat/application/filing/_review.py`
- `src/aeat/application/filing/__init__.py`
- `src/aeat/application/filing/_testing_registry.py`
- `src/aeat/application/workflow/_errors.py`
- `src/aeat/application/workflow/__init__.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/entrypoints/cli/_overview.py`
- `src/aeat/core/errors/registry/_application.py`
- Test files listed above
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

Targeted slices pass on the migrated surfaces:

- `pytest src/aeat/application/aggregation src/aeat/application/review src/aeat/application/filing src/aeat/application/invoices src/aeat/application/overview src/aeat/domain/transactions src/aeat/domain/invoices` — green for migrated tests
- `pytest src/aeat/application/workflow/test_transaction_catalogue_resolution.py` — green
- `pytest src/aeat/entrypoints/cli/test_workflow_surface.py src/aeat/entrypoints/cli/test_cli_surface.py` — green after activating a profile in the ledger-import round-trip test

Pre-existing unrelated failures: `test_complementaria.py` / `test_modelo_303_390.py` (registry casilla-13 input rules), `test_catalogue.py::test_catalogue_carries_supported_entries`, `test_config_setter.py` (older `ProfileBucketPointer` storage shape and CLI help expectations), `test_drafts_pending_emits_high_severity_for_approval_stale` (`aeat review show` vs `aeat app review show` drill-command prefix). Confirmed pre-existing by stashing this commit and reproducing the same failures.
