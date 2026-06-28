---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S210]]'
---

# `secure-storage-production-hardening` `W12.P26.S210` Review

## S210-001 | PASS | Runtime helper owns no plaintext storage

`src/aeat/application/filing/_runtime_repository.py` only resolves a bucket id
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

- `uv run --no-sync pytest -q src/aeat/application/filing/test_runtime_repository.py` passed with 5 tests.
- `uv run --no-sync ruff check src/aeat/application/filing/_runtime_repository.py src/aeat/application/filing/test_runtime_repository.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/filing/test_runtime_repository.py src/aeat/application/filing/test_review_runtime_storage.py` passed with 7 tests.
- `uv run --no-sync ruff check src/aeat/application/filing/_runtime_repository.py src/aeat/application/filing/_history_repository.py src/aeat/application/filing/_review.py src/aeat/application/filing/test_runtime_repository.py src/aeat/application/filing/test_review_runtime_storage.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S210
slice.

Disposition: close `AFR-108` as `runtime-default`.

Follow-up note: the domain filing runtime helper retains the same resolution
shape and is intentionally left to `AFR-238`, where the domain boundary can be
reviewed without widening the S210 application-row commit.
