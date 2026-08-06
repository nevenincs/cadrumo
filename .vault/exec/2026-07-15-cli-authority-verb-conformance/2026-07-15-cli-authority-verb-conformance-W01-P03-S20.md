---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:ecc9034c03c6773a40dc1638e734ab50caebe0350da3c89c7c1b98f761df2534'
step_id: 'S20'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run the focused M210 IRNR real-storage suite after making both injection points required

## Scope

- `src/cadrumo/application/aggregation/tests/test_m210_irnr_income_ledger.py`

## Description

- Confirm `aggregate_irnr_income_ledger_from_repositories` and `LedgerIrnrIncomeAggregationSourceResolver` both require an injected `TransactionCatalogueRepositoryProtocol`.
- Confirm the calculation composition root supplies its shared `_MemoizedTransactionCatalogueRepository` to the M210 resolver.
- Run the requested M210, memoized-repository, and resolver-enrollment files serially with `uv run --no-sync pytest -vv -n 0`.

## Outcome

All 12 collected nodes passed in 54.69 seconds.

The three M210 nodes passed: `test_bucket_calculation_uses_injected_transaction_store_over_distinct_ambient_store`, `test_secure_store_keeps_explicit_classification_and_source_mutation_changes_admission`, and `test_m210_gross_income_source_mode_keeps_manual_and_ledger_authority_exclusive`. The distinct-store node creates a separate injected SQL engine, seeds the transaction only there, leaves the same-bucket ambient repository absent, and proves the public calculation returns the injected amount, transaction identifier, and provenance while the ambient repository remains absent.

The five memoized-repository nodes passed: `test_load_cache_keeps_initial_catalogue_after_storage_changes`, `test_date_range_cache_is_keyed_by_exact_window`, `test_full_load_and_date_range_caches_are_independent`, `test_partition_cache_is_keyed_by_exact_window`, and `test_exists_save_and_bucket_id_delegate_to_concrete_repository`.

The four enrollment nodes passed: `test_every_discovered_resolver_is_enrolled_or_classified`, `test_enrolled_resolvers_exist_and_satisfy_the_protocol`, `test_known_non_mesh_resolvers_still_exported`, and `test_discovery_count_is_pinned`.

## Notes

No source or test file was changed. No incidents or skipped verification.
