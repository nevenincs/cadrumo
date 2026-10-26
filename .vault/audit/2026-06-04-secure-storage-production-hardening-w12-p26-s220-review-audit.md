---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:56a4acd1d0b7bb57751ff9455e359dc1b61cbde03c219e661299a511d08e3e04'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S220` Review

## S220-001 | PASS | Legacy JSONL classification is stale

`W17.P37.S425` already migrated payable and collectible business-operation
invoice persistence from bucket-local JSONL into the
`ledger_business_operation_invoices` secure-object namespace. The S220 register
row was therefore corrected to `runtime-default`.

## S220-002 | FIXED | Default event history now resolves after bucket selection

The service previously created `BucketEventHistoryRepository()` in
`__init__()`, before mutating calls supplied a bucket. The service now keeps
only injected repositories at construction time; when no repository is injected,
each mutating operation creates event history through
`secure_object_repository_for_bucket(bucket_id, settings)`.

## S220-003 | PASS | Validation

- the historical check passed.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for S220.

Disposition: close `AFR-118` as `runtime-default`.
