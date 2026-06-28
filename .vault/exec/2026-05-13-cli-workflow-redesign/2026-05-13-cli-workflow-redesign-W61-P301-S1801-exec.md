---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W61.P301.S1801'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w61-p301-s1801-ledger-storage-ownership-audit]]"
---

# `cli-workflow-redesign` `W61.P301.S1801`

Closed plan rows:

- `W61.P301.S1801`

## Description

Audited the transaction catalogue storage ownership and the active profile bucket plumbing. Produced findings A-E in the linked audit report, with concrete recommendations for S1802-S1806.

Headline defect (Finding A, CRITICAL): `src/aeat/domain/transactions/_repository.py` writes every operator profile's transaction catalogue to one global object key (`namespace="aeat.domain.transactions"`, `object_key="catalogue"`). All eight production call sites that construct `TransactionCatalogueRepository()` inherit the global routing.

Available active-bucket signal (Finding B, HIGH): `WorkflowState.active_profile_bucket_id()` already returns the correct bucket id; the repository simply does not consume it.

Established pattern to mirror (Finding C, MEDIUM): `ProfileBucketRepository` already encodes per-profile object keys (`profile-bucket:{bucket_id}`) inside a `aeat.application.profile.bucket` namespace. The transaction catalogue should follow the same shape (`transaction-catalogue:{bucket_id}` inside `aeat.domain.transactions.bucket`).

Idempotency contract narrowing (Finding D, MEDIUM): `derive_transaction_id` is content-derived and profile-agnostic. After bucket-scoping, `tx_id` is unique per bucket only; cross-bucket consumers must qualify with `(bucket_id, tx_id)`.

Observability hygiene (Finding E, LOW): `ImportSummary.catalogue_path` must carry the bucket id in its URI so import receipts identify the receiving bucket.

## Modified Paths

- `.vault/audit/2026-05-13-cli-workflow-redesign-W61-P301-S1801-ledger-storage-ownership-audit.md` (created)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

No source changes. The audit is purely investigative; verification is the grep evidence cited in each finding.
