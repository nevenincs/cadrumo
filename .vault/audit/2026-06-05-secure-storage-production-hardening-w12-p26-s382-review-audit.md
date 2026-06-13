---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S382]]'
---

# `secure-storage-production-hardening` `W12.P26.S382` Review

## S382-001 | PASS | Ledger remains an intended active-profile CLI surface

The ledger CLI resolves its transaction repository through shared `_tx_repo()` helpers
and passes repository bucket ids into application services. The S382 scanner signal is
therefore expected: ledger is an operator-facing active-bucket surface, not a competing
storage backend.

## S382-002 | FIXED | Ratios extraction carried ambient bucket-event repository construction

The extracted ratios module emitted ratio mutation and censo override-warning events
through default `BucketEventHistoryRepository()` construction. Those paths now pass
`secure_object_repository_for_bucket(bucket_id)` into the event repository, binding
events to the same bucket resolved by the ratios command.

## S382-003 | FIXED | Ratios extraction regressed localized decimal refusal

The extracted ratios parser refused non-decimal input with an English-only f-string.
It now reuses `cli.ledger.errors.invalid_decimal`, and the CLI regression invokes the
real ratios command and asserts the localized message through `tr()`.

## S382-004 | FIXED | Intentional censo mismatch warning needed a debug breadcrumb

`ratios list` intentionally catches `CensoRatioMismatchError` so operators can still see
persisted rows alongside a warning. The catch now logs at debug level with
`exc_info=True`, satisfying the no-silent-swallowing convention while preserving the
operator-facing warning behavior.

## S382-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_ratios_cli.py src/aeat/entrypoints/cli/tests/test_ratios_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_ratios_verbs.py` passed.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ratios_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_ratios_verbs.py` passed with 24 tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S382 slice.

Disposition: close `AFR-280` as `manifest-discovery`.
