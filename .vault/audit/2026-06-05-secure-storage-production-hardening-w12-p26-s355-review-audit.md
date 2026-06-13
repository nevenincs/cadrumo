---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S355]]'
---

# `secure-storage-production-hardening` `W12.P26.S355` Review

## S355-001 | PASS | Filing records use runtime-owned secure objects

`ModeloRecordCatalogueRepository` resolves a bucket through
`resolve_modelo_repository_bucket_id` and defaults to
`secure_objects_for_modelo_bucket`, which delegates to the storage runtime's
bucket-bound secure-object repository factory. This satisfies the runtime-default
target for production construction.

## S355-002 | PASS | Persisted data is FINANCIAL and envelope-versioned

The repository saves and loads the singleton filing-record catalogue under the stable
`aeat.domain.modelos.filing_records` namespace, object key `catalogue`, schema version
1, and `SensitivityClass.FINANCIAL`. The sensitivity-class pinning test covers the
repository source, and the roundtrip tests exercise encrypted storage.

## S355-003 | PASS | Persistence errors use localized structured output

The load path no longer raises `ModeloRecordPersistenceError` with raw interpolated
storage exception text. Integrity, classification, and unsupported inner
envelope-version failures now carry the centralized
`errors.fail.fail_modelo_filing_record_persistence` locale key and redacted context
fields such as reason, cause type, expected class, actual class, and version numbers.

## S355-004 | PASS | Tests are real behavior and non-tautological

The added tests write real encrypted secure-object payloads through the runtime-owned
repository exposed by `isolated_runtime_profile`. They do not use fakes, mocks, stubs,
monkeypatches, skips, or mirrored business logic. The wrong-classification and
future-envelope-version cases would fail if the repository stopped surfacing localized
typed errors.

## S355-005 | PASS | Locale drift repaired through canonical CLI

`python -m aeat.locales audit` initially failed on missing
`cli.app.live.expedientes.capture_all_help`,
`cli.app.live.expedientes.capture_all_modelo_help`, and
`cli.app.live.notifications.latest_help`, plus stale extra locale keys. A later audit
also surfaced missing workflow-resume error keys. The catalogues were repaired via
`python -m aeat.locales scaffold`, placeholder workflow-resume leaves were replaced via
`python -m aeat.locales set`, stale `cli.app.modelo.work.resume_invalid_target` leaves
were removed via `python -m aeat.locales remove`, and the follow-up audit passed for
`ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

## S355-006 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/modelos/_filing_repository.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/_runtime_repository.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_repository_sensitivity_class.py` passed with 10 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"` passed with 10 selected tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed after scaffold repair.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with only the known `PLAN022` warning.

Reviewer note: no critical, high, medium, or low runtime-storage findings remain for
the S355 slice. RAG search was unavailable for the reason recorded in the step record.

Disposition: close `AFR-253` as `runtime-default`.
