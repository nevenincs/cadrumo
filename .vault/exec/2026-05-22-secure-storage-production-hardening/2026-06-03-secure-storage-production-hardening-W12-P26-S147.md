---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S147'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s147-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S147`

Closed `AFR-045` for profile asset and amortization ledger persistence.

## Description

- Reviewed `src/aeat/adapters/persistence/profile/assets.py` against the `secure-object`, `plain-file`, and `remote-provider` scanner signals.
- Kept the repository enrolled in the registered FINANCIAL secure-object namespaces for asset and amortization ledgers.
- Replaced local schema-version and default-object-key literals with values derived from the namespace definitions.
- Added a centralized `secure_object_logical_path()` helper backed by the storage path registry's `secure_objects_table` grammar, and routed asset logical marker paths through it.
- Replaced raw UTF-8 literals in the repository and related corruption tests with `UTF_8_ENCODING`.
- Added localized `AssetRecordError` messages and structured contexts for asset ledger load failure, amortization ledger load failure, and duplicate asset refusal.
- Added sanitized debug logging before wrapping secure-object load failures so adapter-boundary failures are not swallowed silently.
- Added a real isolated-runtime duplicate-asset test asserting the typed localized refusal.
- Removed stale private `_LEDGER_OBJECT_KEY` test coupling by switching corruption tests to the asset-specific registry-derived key.
- Closed `W12.P26.S147` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-045` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/profile/test_assets.py src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/storage/test_namespace_registry.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "assets or secure_object_logical_path or namespace_registry_error"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/profile/assets.py src/aeat/adapters/persistence/profile/test_assets.py src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `rg -n 'Settings\(|os\.environ|print\(|typer\.echo|# noqa|pragma|type: ignore|monkeypatch|_Fake|_Stub|skip\(|xfail|except Exception|except BaseException|contextlib\.suppress|"utf-8"|Path\("db://secure_objects"\)' src/aeat/adapters/persistence/profile/assets.py src/aeat/adapters/persistence/profile/test_assets.py src/aeat/adapters/persistence/profile/test_assets_roundtrip.py src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/__init__.py src/aeat/adapters/persistence/storage/test_namespace_registry.py`

## Notes

`PROJECT_ROOT` remains in `src/aeat/adapters/persistence/storage/test_namespace_registry.py` for central source-tree discovery in an existing registry coverage test; it is imported from `aeat.core.paths` and is not local environment wrangling.
