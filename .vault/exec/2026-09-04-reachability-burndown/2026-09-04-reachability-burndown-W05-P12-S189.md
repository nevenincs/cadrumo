---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:aca9daa7be7ab638a1c4b02153eb366628b121604ad1664fe8b880e066741b26'
step_id: 'S189'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only scalar activity-asset and amortization ledger slice end to end—repositories, domain records, secure namespaces, error registrations, API pages, self-tests, and the bienes-inversión pass-through cross-reference to its deleted record—amending both accepted decisions so any future validated activity schedule lands atomically while finca and bienes-inversión retain their distinct live owners; delete the hand-maintained active-bucket coverage-disposition census exposed by the withdrawal.

## Scope

- `Activity asset domain and persistence slice`
- `bienes-inversión record and CLI projection`
- `storage namespace authority and retained conformance fixtures`
- `central error registry and locale catalogues`
- `CLI-owned API documentation`
- `amortization and bienes-inversión ADRs`
- `production-metastate and focused storage/registry gates`
- `exact reachability signal`
- `and independent code review.`

## Changes

- `D` `src/cadrumo/adapters/persistence/profile/assets.py`
- `D` `src/cadrumo/domain/contribuyente/assets/__init__.py`
- `D` `src/cadrumo/domain/contribuyente/assets/records.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_assets.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_assets_concurrent_add.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_assets_identifier_uniqueness.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_assets_namespace_binding.py`
- `D` `src/cadrumo/adapters/persistence/profile/tests/test_assets_roundtrip.py`
- `D` `src/cadrumo/adapters/persistence/storage/tests/test_active_bucket_consumer_coverage.py`
- `M` `src/cadrumo/adapters/persistence/profile/__init__.py`
- `M` `src/cadrumo/adapters/persistence/profile/bienes_inversion.py`
- `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/_runtime_attached_repositories_support.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_runtime_attached_repositories_part1.py`
- `M` `src/cadrumo/adapters/persistence/storage/tests/test_ephemeral_key_hygiene.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_singleton_mutation_routing.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_secure_model_document.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_bienes_inversion_roundtrip.py`
- `M` `src/cadrumo/core/errors/registry/_domain_part3.py`
- `M` `src/cadrumo/domain/contribuyente/errors.py`
- `M` `src/cadrumo/domain/bienes_inversion/register.py`
- `M` `src/cadrumo/application/bienes_inversion/declare_command.py`
- `M` `src/cadrumo/application/bienes_inversion/tests/test_declare_command.py`
- `M` `src/cadrumo/entrypoints/cli/_bienes_inversion_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_app_ledger_bienes_inversion_command_specs.py`
- `M` `src/cadrumo/locales/en/adapters.yml`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/adapters.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/adapters.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/adapters.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `.vault/adr/2026-08-23-amortization-casilla-mapping-adr.md`
- `M` `.vault/adr/2026-07-01-iva-bienes-inversion-regularizacion-adr.md`
- `D` `docs/api/cadrumo.adapters.persistence.profile.assets.rst`
- `D` `docs/api/cadrumo.domain.contribuyente.assets.rst`
- `D` `docs/api/cadrumo.domain.contribuyente.assets.records.rst`
- `M` `docs/api/cadrumo.adapters.persistence.profile.rst`
- `M` `docs/api/cadrumo.domain.contribuyente.rst`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/bienes_inversion src/cadrumo/application/bienes_inversion src/cadrumo/entrypoints/cli/_bienes_inversion_payloads.py src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py src/cadrumo/entrypoints/cli/_app_ledger_bienes_inversion_command_specs.py src/cadrumo/adapters/persistence/profile/bienes_inversion.py src/cadrumo/adapters/persistence/storage src/cadrumo/core/errors/registry/_domain_part3.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/bienes_inversion/tests/test_declare_command.py src/cadrumo/adapters/persistence/profile/tests/test_bienes_inversion_roundtrip.py src/cadrumo/entrypoints/cli/tests/test_bienes_inversion_cli.py src/cadrumo/adapters/persistence/storage/tests/test_ephemeral_key_hygiene.py src/cadrumo/adapters/persistence/profile/tests/test_singleton_mutation_routing.py src/cadrumo/adapters/persistence/profile/tests/test_secure_model_document.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/docs/tests/test_api_stubs.py` -> `pass`
- `verify:` `mcp__vaultspec_core__check({"feature":"amortization-casilla-mapping","fix":false})` -> `pass`
- `verify:` `mcp__vaultspec_core__check({"feature":"iva-bienes-inversion-regularizacion","fix":false})` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail`
- `verify:` `uv run --no-sync python -m dev.locales audit` -> `fail`

## Notes

- The exact reachability gate reports 341 exact unused symbols and 18 orphan test modules; S189 reduced the signal from 343 to 341 without a baseline, threshold, or disposition-list change.
- The locale audit reports only peer-owned drift in every locale: missing `tui.declarations.lifecycle.verification_refused`, extra `adapters.sede.errors.cotejo_nav_failed`, and extra `aggregation.source_mesh.errors.ambiguous_source_disposition`. No removed activity-asset or bienes-inversión CLI key remains.
- The API scaffold command also synchronized unrelated shared-worktree stubs; only the five directly S189-owned API paths above are attributed to this Step.
