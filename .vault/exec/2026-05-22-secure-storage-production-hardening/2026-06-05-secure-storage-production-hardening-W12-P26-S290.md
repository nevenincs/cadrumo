---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S290'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S290 - Close AFR-188 for core config

Scope: close `AFR-188` for `src/aeat/core/config.py` with signals `active-profile`,
`manifest-bucket`, `master-key`, `sql-route`, `plain-file`, and `remote-provider`;
target `remote-mirror`; owner `W12.P24.S98`.

## Description

- Audited the central `Settings` model, active bucket database URL derivation, storage
  route classification, named bucket route helper, master-key settings, and outbound
  storage provider settings.
- Added debug logging and a typed `ActiveProfilePointerError` refusal so corrupt
  active-profile pointer reads do not silently degrade to the root fallback route.
- Added a real corrupt-pointer regression covering the typed refusal and exception
  chaining without mocks, monkeypatching, stubs, skips, xfails, or mirrored logic.
- Replaced an in-process direct `AEAT_OUTPUT_LANGUAGE` mutation in the CLI reference
  generator with `override_settings(aeat_output_language="en")`.
- Included the central live-read opt-in constant and timeout settings as declarative
  config fields for access-gate and live-auth consumers.
- Ran vaultspec RAG semantic searches for route resolver, pointer fallback, provider,
  master-key, and remote storage settings duplication.
- Closed `W12.P26.S290` through `vaultspec-core vault plan step check` and updated
  the `AFR-188` register status to `closed`.

## Outcome

`AFR-188` is closed as the central runtime settings and route-derivation surface. The
secure bucket rollout now refuses corrupt active-profile pointer metadata instead of
falling back to root storage, preserves debug evidence for the failure, and removes the
reviewed in-process direct AEAT output-language environment mutation.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/config.py src/aeat/core/test_storage_route_classification.py src/aeat/core/errors/__init__.py src/aeat/core/errors/registry/_core.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/tests/test_config.py src/aeat/core/test_config_override.py src/aeat/core/test_settings_single_surface_invariant.py src/aeat/adapters/persistence/storage/test_runtime.py src/aeat/adapters/outbound/storage/test_factory.py src/aeat/entrypoints/cli/_doc_reference.py src/aeat/entrypoints/cli/test_doc_reference_conformance.py`
- `uv run --no-sync pytest -q src/aeat/core/test_storage_route_classification.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/tests/test_config.py::TestDatabaseUrlDerivation src/aeat/core/test_config_override.py src/aeat/core/test_settings_single_surface_invariant.py src/aeat/adapters/persistence/storage/test_runtime.py::test_runtime_ready_when_route_and_active_session_match src/aeat/adapters/persistence/storage/test_runtime.py::test_runtime_reports_root_fallback_route_as_unready src/aeat/adapters/persistence/storage/test_runtime.py::test_runtime_reports_explicit_database_url_without_public_path_leak src/aeat/adapters/persistence/storage/test_runtime.py::test_default_route_repository_refuses_settings_scoped_active_profile_without_session src/aeat/adapters/persistence/storage/test_runtime.py::test_default_route_repository_refuses_pointer_scoped_active_profile_without_session src/aeat/adapters/outbound/storage/test_factory.py`
- `uv run --no-sync pytest -q -m docs src/aeat/entrypoints/cli/test_doc_reference_drift.py::test_committed_cli_reference_matches_regenerated_output`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "Settings active profile pointer database route root fallback debug log secure bucket config" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "aeat core config storage provider google drive secret store backend master key local storage root settings" --type code --port 8766 --max-results 8`

## Notes

The root-level database fallback remains intentional only for a missing active-profile
selection. A present invalid pointer is now treated as storage metadata corruption and
raises `ActiveProfilePointerError`. The docs-marker conformance file was included in
the command but deselected by the default lane; the executed docs-marker validation was
the drift test run with `-m docs`.
