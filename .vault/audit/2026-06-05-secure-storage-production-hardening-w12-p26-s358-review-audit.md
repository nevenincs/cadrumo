---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S358]]'
---

# `secure-storage-production-hardening` `W12.P26.S358` Review

## S358-001 | PASS | Verification reports use runtime-owned secure objects

`VerificationReportCatalogueRepository` resolves its bucket through the shared modelo
runtime helper and defaults to `secure_objects_for_modelo_bucket`, which delegates to
the storage runtime's bucket-bound secure-object repository factory. No direct SQL
repository construction was introduced.

## S358-002 | PASS | Persisted data is FINANCIAL and envelope-versioned

The repository saves and loads the singleton verification-report catalogue under
`aeat.domain.modelos.verification_reports`, object key `catalogue`, schema version 1,
and `SensitivityClass.FINANCIAL`. Existing roundtrip tests exercise non-default report
fields and invariant drift; the sensitivity-class guard includes the repository source.

## S358-003 | PASS | Persistence errors use localized structured output

Integrity, classification, and unsupported inner envelope-version failures now carry
the centralized `errors.fail.fail_modelo_verification_report_persistence` locale key
and redacted context fields. The storage-integrity catch keeps `exc_info=True` logging
and chains the original exception.

## S358-004 | PASS | Tests are real behavior and non-tautological

The added tests write real encrypted secure-object payloads through the
`isolated_runtime_profile` repository and then load through the repository under test.
They assert typed localized errors for classification drift and future inner envelope
versions without fakes, mocks, stubs, monkeypatches, skips, or mirrored business logic.

## S358-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/modelos/_verification_repository.py src/aeat/domain/modelos/test_verification_report_roundtrip.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py` passed with 10 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"` passed with 10 selected tests.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S358 slice.

Disposition: close `AFR-256` as `runtime-default`.
