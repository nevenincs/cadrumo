---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:c5efc0f8ca454b2d2e88517e997899a24e69e45c2afdd4b848ec5486faaa8140'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S210` Review

## S210-001 | PASS | Runtime helper owns no plaintext storage

The retired module only resolves a bucket id
and delegates repository construction to
`secure_object_repository_for_bucket()`. It does not open files, write
manifests, construct SQL routes directly, read environment variables, or manage
master-key custody.

## S210-002 | PASS | Active-profile refusal is typed and contextual

Both active-profile refusal branches raise `ModeloApplicationError`, which
inherits from the central AEAT error hierarchy through `ModeloDraftError`.
The locale key is centralized as `_NO_ACTIVE_PROFILE_BUCKET_MESSAGE`, and the
two branches now carry separate context reasons:
`blank_explicit_bucket_id` and `missing_active_profile_bucket`.

## S210-003 | PASS | Runtime refusal is covered by real behavior tests

The focused tests cover explicit bucket trimming, blank explicit bucket
refusal, active-profile fallback resolution, missing active profile refusal, and
unready runtime refusal from the secure-object factory. These tests use
settings overrides and the real runtime validation path rather than mocks or
patched repository objects.

## S210-004 | PASS | Validation

- the historical check passed with 5 tests.
- the historical check passed.
- the historical check passed with 7 tests.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S210
slice.

Disposition: close `AFR-108` as `runtime-default`.

Follow-up note: the domain filing runtime helper retains the same resolution
shape and is intentionally left to `AFR-238`, where the domain boundary can be
reviewed without widening the S210 application-row commit.
