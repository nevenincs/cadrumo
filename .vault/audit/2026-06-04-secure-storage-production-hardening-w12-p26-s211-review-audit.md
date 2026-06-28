---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S211]]'
---

# `secure-storage-production-hardening` `W12.P26.S211` Review

## S211-001 | PASS | Testing registry is not a storage authority

`src/aeat/application/filing/_testing_registry.py` builds filing drafts through
the production registry runtime and supplies an empty `TransactionCatalogue`
when approving deterministic test drafts. It does not inspect bucket manifests,
read active-profile settings, open files, construct secure-object repositories,
or write any persistence surface.

## S211-002 | PASS | Test-only bucket id is named

The approval helper now uses `_REGISTRY_TEST_BUCKET_ID` instead of an inline
`"registry-test"` literal. The value is still intentionally test-only, but its
role is now visible at module scope rather than buried in the approval call.

## S211-003 | PASS | Existing tests are real helper behavior

`test_testing_registry.py` exercises the actual helper and production registry
builder path. It checks frozen draft construction, approved and non-approved
metadata, unsupported-modelo refusal, duplicate input refusal, registry value
projection, deterministic draft ids, and decimal coercion without mocks,
patches, skips, xfails, fake repositories, or mirrored calculation logic.

## S211-004 | PASS | Validation

- `uv run --no-sync pytest -q src/aeat/application/filing/test_testing_registry.py` passed with 11 tests.
- `uv run --no-sync ruff check src/aeat/application/filing/_testing_registry.py src/aeat/application/filing/test_testing_registry.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S211
slice.

Disposition: close `AFR-109` as `manifest-discovery`.
