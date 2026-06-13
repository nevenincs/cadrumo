---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening-W04-P08-S32` Code Review

W04-P08-S32-001 | MEDIUM | Explicit partial-read diagnostics still abort on some row-level contract failures
`iter_records_with_failures` now preserves per-row diagnostics for decryption failures and unknown classifications, but it still raises `ClassificationError`, `EnvelopeVersionError`, or registered-schema `EnvelopeVersionError` for classification mismatches and unsupported schema versions instead of returning a typed `SecureObjectUnreadable` row. This means the explicit partial-read API is not fully fault-isolated for metadata contract drift, despite its own docstring saying metadata failures are represented by `SecureObjectUnreadable`, and despite the ADR requirement for typed per-row success and failure diagnostics. The default `list_records` path still fails closed without yielding a readable subset because it buffers before yielding, so this is not a partial-plaintext leakage blocker for S32. It should be owned before W04.P08 diagnostic propagation is treated as complete.

W04-P08-S32-002 | LOW | Partial-subset leakage test relies on natural-key names that do not define storage order
`test_list_records_does_not_yield_readable_subset_before_unreadable_failure` names one key with `a-` and one with `z-`, but `object_key` is stored as a master-key-derived HMAC digest and `iter_records_with_failures` orders by that digest. The test still proves the current implementation raises on the first `next()` instead of yielding a readable row, and it is not tautological, but it does not deterministically place the readable row before the unreadable row. A future streaming regression that raises only after a later unreadable row could escape if the digest order puts the unreadable row first.

W04-P08-S32-PASS | INFO | No HIGH or CRITICAL blockers found for the S32 commit
The reviewed change makes `list_records` fail closed on decryption-unreadable rows, preserves the explicit mixed-result path through `iter_records_with_failures`, does not log or return plaintext/object natural keys on failure, and the focused listing tests pass under `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -k "list_records or iter_records_with_failures"`.

W04-P08-S32-REREVIEW-001 | MEDIUM | Registry-bound schema drift still escapes the explicit diagnostic iterator
Re-review confirms the direct metadata checks from `W04-P08-S32-001` are remediated: classification mismatches and caller `max_supported_version` drift now yield `SecureObjectUnreadable`, and the new metadata-contract test covers those paths. One row-level metadata path still raises directly: after those typed outcomes, `iter_records_with_failures` calls `_enforce_registered_row_schema`, which raises `EnvelopeVersionError` when a registry-bound namespace contains a row newer than the registered schema. Because the ADR makes the namespace registry mandatory and requires partial listing to return typed per-row diagnostics, this remains a diagnostic-path gap for governed namespaces. It does not leak partial readable subsets through `list_records`, which still raises before yielding buffered records.

W04-P08-S32-REREVIEW-002 | RESOLVED | Partial-subset leakage test no longer depends on HMAC digest ordering
`W04-P08-S32-002` is resolved. The test now mutates on-disk classification metadata for the stored row and asserts `list_records` raises `SecureObjectUnreadableError` on first iteration without relying on natural-key lexical order, which is not the persisted ordering for the HMAC-digested `object_key` column.

W04-P08-S32-REREVIEW-PASS | INFO | Re-review found no HIGH or CRITICAL blocker
Focused validation passed with `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` and `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -k "list_records or iter_records_with_failures"`. The remaining issue is scoped to explicit registry-bound diagnostics, not default-list fail-closed behavior or partial-readable subset leakage.

W04-P08-S32-FINAL-REREVIEW | PASS | No S32 findings remain
Final re-review confirms `W04-P08-S32-REREVIEW-001` is resolved. `iter_records_with_failures` now catches registry-bound row schema drift from `_enforce_registered_row_schema` and yields a typed `SecureObjectUnreadable` instead of aborting the explicit partial-read iterator. The new real-registry regression test covers that path with `StorageHierarchyRegistry` bound to the repository. The default `list_records` path remains fail-closed before yielding any readable subset, and the explicit diagnostic iterator now preserves row-level diagnostics for decryption failures, unknown classifications, classification mismatches, caller-supported-version drift, and registry-schema drift. Focused validation passed with `uv run ruff check src/aeat/adapters/persistence/storage/sql/secure_objects.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` and `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py -k "list_records or iter_records_with_failures"`; the pytest selection reported 9 passed and 27 deselected.
