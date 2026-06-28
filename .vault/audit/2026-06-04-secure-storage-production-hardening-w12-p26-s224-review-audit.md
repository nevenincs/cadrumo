---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S224]]'
---

# `secure-storage-production-hardening` `W12.P26.S224` Review

## S224-001 | PASS | Ratio commands delegate to runtime-backed storage

`set_usage_ratio`, `unset_usage_ratio`, `list_eligible_ratios_for_bucket`, and
`validate_ratios_for_bucket` do not open files, inspect environment variables,
or construct storage directly. They call `load_usage_ratios` and
`save_usage_ratios` with an explicit `bucket_id`; the domain service resolves
the runtime-owned secure-object repository for that bucket.

## S224-002 | PASS | Application facade has real runtime coverage

The new tests provision a real active runtime bucket, exercise the public
application wrappers, and assert both successful round-trip behavior and
fail-closed behavior when a caller requests a different bucket than the active
runtime route.

## S224-003 | PASS | Error and localization disposition

Usage-ratio exceptions derive from the project `AeatError` family. The CLI
handler for the known unset-no-override path translates the operator-facing
message through `tr()`. This step did not add new operator-facing raw strings.

## S224-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/ledger/_ratios.py src/aeat/application/ledger/test_ratios.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/ledger/test_ratios.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` returned only the existing monotonic-order warning.

Reviewer note: no critical, high, medium, or low findings remain for S224.

Disposition: close `AFR-122` as `runtime-default`.
