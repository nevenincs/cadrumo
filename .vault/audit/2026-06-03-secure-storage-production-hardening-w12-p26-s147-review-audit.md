---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S147]]'
---

# `secure-storage-production-hardening` `W12.P26.S147` Review

## S147-001 | PASS | Profile assets remain enrolled in secure-object namespaces

The asset and amortization repositories continue to save and load through `SecureObjectRepository` under the registered FINANCIAL namespaces `profile_assets_ledger` and `profile_assets_amortization_ledger`.

Resolution: the adapter now derives namespace, schema version, and singleton object keys from the namespace definitions instead of duplicating local literals.

## S147-002 | PASS | Logical SQL marker paths are centralized

The asset repository previously constructed `Path("db://secure_objects")` markers locally. The storage hierarchy registry already declares the `secure_objects_table` logical SQL grammar.

Resolution: `secure_object_logical_path()` now renders logical SQL markers from the registered grammar, is exported through the storage package, and the asset repository uses it for envelope and lock marker paths.

## S147-003 | PASS | Adapter-boundary asset errors are localized and observable

Asset ledger load failures, amortization load failures, and duplicate asset refusals previously surfaced raw English messages only. Load failures also wrapped lower-level storage exceptions without leaving debug evidence.

Resolution: those `AssetRecordError` paths now carry `translated_message` keys and structured context. Load wrappers emit sanitized debug entries containing namespace, object key, and error type before raising the typed domain error.

## S147-004 | PASS | Encoding and test suppressions were removed

The repository and adjacent corruption tests used raw UTF-8 literals, and the touched namespace registry test file carried `type: ignore` suppressions in local Pydantic helper constructors.

Resolution: repository/test JSON encoding now uses `UTF_8_ENCODING`; the Pydantic helper constructors now use `model_validate()` and no longer need suppressions.

## S147-005 | PASS | Tests exercise real secure SQL behavior

The new duplicate-asset test uses the real isolated runtime profile and repository, inserts an asset, attempts a duplicate insert, and asserts the typed localized refusal context. Existing roundtrip/corruption tests continue to manipulate real encrypted secure-object rows.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/profile/test_assets.py src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "assets or secure_object_logical_path or namespace_registry_error"` passed with 25 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/profile/assets.py src/aeat/adapters/persistence/profile/test_assets.py src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed after locale updates through `python -m aeat.locales scaffold` and `python -m aeat.locales set`.
- The touched-file source scan found no direct settings construction, environment access, print/typer output, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, broad exception catches, raw UTF-8 literals, or local `Path("db://secure_objects")` construction.

Disposition: close `AFR-045` as `remote-mirror`.
