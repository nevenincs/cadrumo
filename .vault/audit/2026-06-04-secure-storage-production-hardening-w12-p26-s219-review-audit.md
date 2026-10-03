---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:badf98015e9b96b4cf225e3350105f36cb1a74f145f0159483a7cc0bbef4b81b'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S219` Review

## S219-001 | FIXED | Bucket-event history defaults now use the requested bucket

Ledger actions previously defaulted `BucketEventHistoryRepository()` through
the active-bucket repository factory while transaction and invoice catalogues
were bound to the command or query bucket. Default event-history access now
uses `secure_object_repository_for_bucket(bucket_id)`, so event persistence
shares the same requested bucket authority and fails closed when the live
session cannot serve that bucket.

## S219-002 | PASS | Regression covers an adverse runtime mismatch

The added test uses a real secure SQL runtime and a real transaction repository
bound to a non-active command bucket through an injected secure-object backend.
With no injected event repository, the ledger create path now raises the storage
runtime mismatch instead of writing audit history through the ambient active
profile.

## S219-003 | LOW | Existing raw ledger validation messages remain outside this storage slice

The retired module still has pre-existing
`TransactionValidationError` construction sites that pass raw strings in
provider/source validation and some ledger workflow guards. These were not
introduced by S219 and do not change the runtime-default storage disposition,
but they should be handled by a dedicated localization/error-surface follow-up
using the canonical `python -m aeat.locales` CLI.

## S219-004 | PASS | Validation

- the historical check passed.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-117` as `runtime-default`; no critical, high, or medium
findings remain for the secure-storage disposition.
