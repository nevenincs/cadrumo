---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-research]]'
---

# `cli-workflow-redesign` `W61.P301.S1801` Audit — Active Profile Bucket and Transaction Catalogue Storage Ownership

## Finding W61-P301-S1801-A | CRITICAL | Transaction catalogue is stored under a single global object key with no profile-bucket scoping.

`src/aeat/domain/transactions/_repository.py` declares module-level constants `_TX_NAMESPACE = "aeat.domain.transactions"` and `_TX_OBJECT_KEY = "catalogue"` (lines 38-39). Every `TransactionCatalogueRepository` instance reads and writes the same `(namespace, object_key)` pair via `SecureObjectRepository`, regardless of which profile is active. As a result, all imported and manual transactions across every operator profile share one encrypted FINANCIAL-class blob.

This contradicts the apex bucket invariant from `2026-05-12-cli-workflow-redesign-bucket-adr`: durable per-profile artifacts must live inside the active profile's secure bucket so that switching profiles, deleting a profile, or exporting per-profile data has clean boundaries. Today, switching profiles does not switch ledger storage; deleting a profile does not delete its transactions; cross-profile collisions on `derive_transaction_id` SHA-256 would silently merge unrelated operators' rows.

## Finding W61-P301-S1801-B | HIGH | Active profile bucket id is reachable via WorkflowState but is not threaded into the transaction repository.

`src/aeat/application/workflow/_models.py` exposes `WorkflowState.active_profile_bucket_id() -> str | None` (lines 161-168) and `WorkflowState.profiles: dict[str, ProfileBucketPointer]` (line 142). The application layer already has a canonical answer for "which bucket is active". `TransactionCatalogueRepository.__init__` accepts only an optional `SecureObjectRepository` and does not consume a bucket id, so the answer is never plumbed through. Every caller of `TransactionCatalogueRepository()` writes to the global catalogue object key.

Affected call sites that construct `TransactionCatalogueRepository()` directly:

- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/application/review/_adapters.py`
- `src/aeat/application/overview/__init__.py`
- `src/aeat/application/filing/_review.py`
- `src/aeat/application/aggregation/_renta_ledger.py`
- `src/aeat/application/invoices/_queries.py`
- `src/aeat/application/invoices/_linking.py`
- `src/aeat/application/invoices/_reconciliation.py`

(Test-side constructors in `application/review/test_aggregator.py`, `application/review/test_adapters.py`, `application/aggregation/test_renta_ledger.py`, `domain/invoices/test_reconciliation.py`, `domain/invoices/test_repository.py` will need parallel parameterisation when production sites adopt bucket-scoped construction.)

## Finding W61-P301-S1801-C | MEDIUM | The profile-bucket repository already encodes per-profile object keys; the pattern is established.

`src/aeat/application/profile/_repository.py:50` defines `profile_bucket_object_key(profile_name) = f"profile-bucket:{profile_bucket_id(profile_name)}"`, and `ProfileBucketRepository.load`/`.save`/`.delete` route through that per-profile key inside the `aeat.application.profile.bucket` namespace. The transaction catalogue needs the same shape — a per-bucket object key inside a stable namespace — so that one profile's catalogue is fully isolated from another.

Concretely the contract for S1802 should mirror the profile bucket: a `transaction_catalogue_object_key(bucket_id)` helper that returns `f"transaction-catalogue:{bucket_id}"`, with a namespace such as `aeat.domain.transactions.bucket` so the migration is unambiguous and the rule "ledger storage = bucket-scoped" is enforceable by inspection.

## Finding W61-P301-S1801-D | MEDIUM | Idempotency hash is profile-agnostic and will collide on identical raw rows across profiles.

`derive_transaction_id(raw_transaction)` in `src/aeat/domain/transactions/_models.py` hashes the `RawTransaction` content — it does not incorporate the owning bucket id. Today the single global catalogue silently absorbs the collision (same id → "skipped"); after bucket-scoping the catalogue, two operators importing the same row in their own buckets will keep separate blobs but will independently use the same id — that is acceptable per bucket, but cross-bucket queries that walk catalogues must not assume `tx_id` is globally unique. S1804 ("prevent cross-profile transaction collisions") should specify that `tx_id` remains content-derived and unique within a bucket only; consumers that aggregate across buckets must namespace by `(bucket_id, tx_id)`.

## Finding W61-P301-S1801-E | LOW | `ImportSummary.catalogue_path` advertises the global key in its URI and will leak as observability output.

`ImportSummary.catalogue_path = f"db://secure_objects/{_TX_NAMESPACE}/{_TX_OBJECT_KEY}"` (line 207) hardcodes the global object key into the import-result envelope. Operators reading import receipts today see `db://secure_objects/aeat.domain.transactions/catalogue`; after bucket-scoping, the URI should carry the bucket id (e.g., `db://secure_objects/aeat.domain.transactions.bucket/transaction-catalogue:OPERATOR_42`) so that the receipt is unambiguous about which profile bucket received the rows.

## Contract Specification (W61.P301.S1802)

The bucket-scoped transaction catalogue repository contract is fixed as follows. S1803-S1806 must adopt it verbatim.

**Namespace**

`TX_BUCKET_NAMESPACE = "aeat.domain.transactions.bucket"` — a module-level constant exported from `aeat.domain.transactions`.

**Object key helper**

```python
def transaction_catalogue_object_key(bucket_id: str) -> str:
    trimmed = bucket_id.strip()
    if not trimmed:
        raise ValueError("bucket_id must not be blank")
    return f"transaction-catalogue:{trimmed}"
```

**Repository constructor**

`TransactionCatalogueRepository.__init__(*, bucket_id: str, objects: SecureObjectRepository | None = None)`. `bucket_id` is required, non-blank, validated by `transaction_catalogue_object_key`. Every read and write resolves through `TX_BUCKET_NAMESPACE` + `transaction_catalogue_object_key(bucket_id)`; `_TX_NAMESPACE` and `_TX_OBJECT_KEY` are removed.

**Bucket id property**

`TransactionCatalogueRepository.bucket_id: str` — read-only accessor for observability and assertion sites.

**Import summary URI**

`ImportSummary.catalogue_path = f"db://secure_objects/{TX_BUCKET_NAMESPACE}/{transaction_catalogue_object_key(bucket_id)}"`.

**Active bucket resolution**

`aeat.application.workflow` exports `active_bucket_id_or_raise(state: WorkflowState) -> str` (or equivalent named helper) that returns `state.active_profile_bucket_id()` or raises a typed error (Finding F below) when no profile is active. CLI entrypoints call this helper before constructing a repository; pure-application helpers receive `bucket_id` as a required keyword argument.

**Application-layer signatures**

Every `aeat.application.*` helper that today fabricates a `TransactionCatalogueRepository()` fallback when its caller passed `None` must take `bucket_id: str` as a required keyword argument and pass it through to the fallback. Affected: `aggregate_renta_ledger_expenses_from_repositories`, `aeat.application.overview` build_overview, `aeat.application.invoices._reconciliation`, `_linking`, `_queries`, `aeat.application.review._adapters`, `aeat.application.filing._review._load_transaction_catalogue_cached` and `_read_transaction_catalogue`.

**Cache shape**

`@lru_cache(maxsize=8)` on `_load_transaction_catalogue_cached` is keyed on `bucket_id` (the only argument) so per-bucket loads are cached independently and profile switches naturally select a different cache entry.

**Tx-id uniqueness**

`derive_transaction_id(raw_transaction)` remains content-derived. Uniqueness is contract-scoped to one bucket. Cross-bucket consumers MUST qualify with `(bucket_id, tx_id)`.

## Finding W61-P301-S1801-F | MEDIUM | No typed error exists for "ledger operation requested with no active profile".

Today the absence of an active profile is signalled either by `_active_profile_or_exit` (typer.Exit(2)) at the CLI layer or by a generic `_bad(...)` at later boundaries. The bucket-scoped contract needs a typed `LedgerStorageError` subclass (or equivalent typed error in `aeat.core.errors`) so non-CLI callers — application services and tests — can distinguish "no active bucket" from "catalogue empty" or "catalogue corrupted". S1806 should register this error code and log fields.

## Recommendation

S1802 should introduce a `bucket_id: str` constructor argument on `TransactionCatalogueRepository`, with a helper `transaction_catalogue_object_key(bucket_id)` mirroring the profile-bucket helper. S1803 should thread `WorkflowState.active_profile_bucket_id()` into every call-site listed under Finding B, refusing to operate when there is no active profile. S1804 should narrow the `tx_id` uniqueness contract to per-bucket. S1805 should migrate the review and import projections to obtain a repository bound to the active bucket. S1806 should add a dedicated error code (e.g., `ledger.no_active_bucket`) for the "ledger operation requested with no active profile" path.

No source changes were made by this audit step.
