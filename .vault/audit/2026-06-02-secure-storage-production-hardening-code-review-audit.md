---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S49-001 | PASS | Final SecureStorage W06.P11 review found no findings

Reviewer `Beauvoir` completed the final `W06.P11.S49` SecureStorage review across the `S45` through `S48` commit set, step records, audit records, and scoped implementation/test files.

No findings were reported. The review verified that runtime-bound repositories fail closed for missing, stale, expired, or unsecured active sessions; locale-backed error keys are present; exceptions derive from AEAT storage/core bases; and the new tests avoid fakes, mocks, stubs, monkeypatches, skips, xfails, naked environment mutation, and mirrored business logic.

Closure assessment: `W06.P11.S49` can close based on the reviewed evidence. Live Google Drive mirror and formula-level calc-sheets proof remains separately tracked by the open `W06.P11.S428` through `W06.P11.S431` rows and is not claimed by this closeout.

## S431-002 | MEDIUM | RESOLVED | Google Sheets quota failures were generic network errors with no client retry

Live connector reads on 2026-06-02 hit Google Sheets HTTP 429 `ReadRequestsPerMinutePerProject`, but the shared Google API executor called `request.execute()` with no retry count and mapped unmapped HTTP failures to `OutboundStorageNetworkError`. That made quota pressure operationally indistinct from generic transport failure and left the S431 quota-aware claim under-supported.

Resolution: `execute_request` now calls google-api-python-client requests with `num_retries=3` and maps HTTP 429 plus rate-limit HTTP 403 payloads to the existing `OutboundStorageQuotaError`. Focused tests use real `httplib2.Response` plus `googleapiclient.errors.HttpError`, and no fake response / skip path remains in `test_api.py`.

## S43-005 | MEDIUM | RESOLVED | One-hop mirror lineage could not prove multi-revision stale ancestry

The mirror comparator could not prove that a remote root revision more than one local revision behind was an ancestor, so the implementation either had to classify true stale mirrors as conflicts or rely on timestamp-only inference. That left S43's stale-vs-conflict classification incomplete.

Resolution: S440 persists `revision_ancestor_ids` on secure-object rows, exposes the tuple in `SecureObjectRawRow`, includes it in `RemoteMirrorObjectManifest`, and classifies stale mirrors by revision-id ancestry. Real repository tests now prove both the three-save stale case and the unrelated older-root conflict case.

## S425-006 | PASS | Business-operation invoice JSONL store migrated to secure objects

Reviewer `Nash` completed the `W17.P37.S425` review across the business-operation invoice service, namespace registry, namespace coverage tests, and sensitive persistence allowlist change.

No findings were reported. The review verified that payable and collectible business-operation invoice persistence routes through `BusinessOperationInvoiceRepository` and `secure_object_repository_for_bucket`, object keys are bucket/source-kind scoped as `{bucket_id}:{source_kind}`, production JSONL read/write logic is removed, tests use real runtime secure-object behavior without fakes or monkeypatching, and reviewed files do not use naked environment access.

Closure assessment: `W17.P37.S425` can close based on the reviewed evidence. The separate `_iva_compensation_wallet.py` diagnostic write inventory delta remains outside this S425 slice.
