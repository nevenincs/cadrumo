---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S82'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S82 Master Key Storage Verification

Scope: verify master key storage behavior and facade imports after decomposition.

## Description

- Run `uv run --no-sync ruff check` over the touched master-key, storage-test, and custody lifecycle surfaces.
- Run focused master-key behavior tests for provider, error, fail-closed, passphrase, and envelope-document coverage.
- Run the full master-key test package after extraction.
- Run the full storage persistence test package after sensitive-write inventory and smoke-test contract updates.
- Run custody profile lifecycle coverage with the repository marker expression required by the current marker policy.
- Run an import smoke for moved `EphemeralMasterKeyProvider`, `atomic_write_secure_bytes`, and `looks_like_real_tax_id` symbols through their stable master-key import paths.

## Outcome

Ruff passed for the touched master-key, storage-test, and custody lifecycle surfaces. Focused master-key tests passed with 85 tests, the full master-key package passed with 212 tests, the full storage package passed with 264 tests, and custody profile lifecycle coverage passed with 6 tests. The master-key import smoke confirmed the public compatibility aliases still resolve to the extracted helpers.

## Notes

The verification repaired storage-test contract drift discovered by the S82 lane rather than recording false failures: package-smoke imports now target the storage package instead of the tests package, the sensitive write inventory matches the decomposed production write sites, custody lifecycle coverage asserts recovery enrollment in the bucket manifest, and `NoActiveBucketSessionError` renders the locale-backed unlock remediation through `str(error)`.
