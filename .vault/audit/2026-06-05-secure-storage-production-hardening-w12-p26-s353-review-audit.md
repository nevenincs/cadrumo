---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S353]]'
---

# `secure-storage-production-hardening` `W12.P26.S353` Review

## S353-001 | PASS | Calculation revisions use runtime-owned secure objects

`CalculationRevisionCatalogueRepository` resolves a bucket through
`resolve_modelo_repository_bucket_id` and defaults to
`secure_objects_for_modelo_bucket`, which delegates to the storage runtime's
bucket-bound secure-object repository factory. This satisfies the runtime-default
target for production construction.

## S353-002 | PASS | Persisted data is FINANCIAL and envelope-versioned

The repository saves and loads the singleton calculation-revision catalogue under the
stable `aeat.domain.modelos.calculation_revisions` namespace, object key `catalogue`,
schema version 1, and `SensitivityClass.FINANCIAL`. The sensitivity-class pinning test
covers the repository source, and the roundtrip test exercises encrypted storage.

## S353-003 | PASS | Persistence errors use localized structured output

The load path no longer raises `CalculationRevisionPersistenceError` with raw
interpolated storage exception text. Integrity, classification, and unsupported inner
envelope-version failures now carry the centralized
`errors.fail.fail_modelo_calculation_revision_persistence` locale key and redacted
context fields such as reason, cause type, expected class, actual class, and version
numbers.

## S353-004 | PASS | Tests are real behavior and non-tautological

The added tests mutate real encrypted secure-object payloads through the runtime-owned
repository exposed by `isolated_runtime_profile`. They do not use fakes, mocks, stubs,
monkeypatches, skips, or mirrored business logic. The wrong-classification and
future-envelope-version cases would fail if the repository stopped surfacing localized
typed errors.

## S353-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/_runtime_repository.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py` passed with 10 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"` passed with 10 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py src/aeat/domain/modelos/_calculation_repository.py src/aeat/domain/modelos/test_calculation_repository_roundtrip.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync vaultspec-rag search "CalculationRevisionCatalogueRepository secure_objects_for_modelo_bucket runtime bucket FINANCIAL translated persistence error" --type code --port 8766 --max-results 8` returned the repository, runtime helper, and tests.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S353 slice.

Disposition: close `AFR-251` as `runtime-default`.
