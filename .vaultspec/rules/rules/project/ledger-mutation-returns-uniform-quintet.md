---
name: ledger-mutation-returns-uniform-quintet
---

# Ledger mutation returns uniform quintet

## Rule

Every CLI verb that mutates exactly one ledger transaction must return `{bucket_id, transaction_id, bucket_event_ids, review_status, transaction}` through the shared ledger mutation result shape.

## Why

The `2026-06-10-ledger-interface-contract-adr` standardised mutation output because ledger mutation verbs had drifted across add, update, classify, review, and related paths. Operators and downstream automation need one envelope shape to read the changed subject, its review state, and its emitted bucket events. Structural verbs that act on a set or destroy the subject are different operations and must declare their typed exception explicitly.

## How

- Good: `add`, `update`, `classify`, and `review` emit the shared mutation result with bucket id, transaction id, bucket event ids, review status, and a `TransactionPayload`.
- Good: `split`, `merge`, `remove`, and `reset` use their own typed schemas because they operate on multiple rows or destroy the subject.
- Bad: adding a single-transaction mutation verb that returns only `transaction_id` or only the updated transaction.
- Bad: duplicating the quintet fields in a new ad hoc payload instead of using the shared shape.
