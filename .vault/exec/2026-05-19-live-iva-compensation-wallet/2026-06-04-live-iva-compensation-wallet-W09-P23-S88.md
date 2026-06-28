---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S88'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W09.P23.S88 Test Literal Centralization

Scope: close the broad test constants remediation step for AEAT/Sede host and route literals.

## Description

- Inventory test-suite AEAT/Sede host and route literals with an AST scan that separates docstrings from executable string constants.
- Migrate executable URL/path expectations to `Settings.external_constants()` or helpers backed by that registry.
- Keep unsafe/wrong-host/path canaries behind the declared `aeat.tests.aeat_literal_fixtures` boundary.
- Add a broad static guard that scans the full test tree for non-docstring AEAT/Sede literals outside declared authority files.
- Enroll missing actual Sede service paths in the typed external constants schema for R210 simulator, Renta borrador detail, declaration consult, and Cl@ve login surfaces.
- Continue the broad test migration through justificante, portal/manual, registry, live application, workflow, persistence, CLI, and auth suites until the AST inventory is zero.
- Close `W09.P23.S88` with the vault plan CLI.

## Outcome

S88 is complete. Test literals are centralized or declared behind the fixture/canary boundary. The final all-string AST inventory is `TOTAL=0` outside `aeat.tests.aeat_literal_fixtures` and the scanner authority in `test_external_constants.py`.

Validation passed:

- `pytest -q src/aeat/core/test_external_constants.py::test_test_suite_aeat_route_literals_are_centralized_or_declared src/aeat/core/test_external_constants.py::test_remote_guard_parity_and_oracle_tests_use_declared_aeat_literal_fixtures src/aeat/core/test_external_constants.py::test_portal_registry_modules_do_not_reintroduce_route_or_host_literals src/aeat/domain/calculations/registry/test_referential_integrity.py`
- `ruff check src/aeat/core/test_external_constants.py src/aeat/domain/calculations/registry/test_referential_integrity.py`
- `uv run ruff check ...` on the S88-touched core, fixture, application, persistence, CLI, and auth files.
- `uv run pytest -q src/aeat/adapters/inbound/justificante/test_extract_modelos.py src/aeat/adapters/inbound/justificante/test_parser.py src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py src/aeat/domain/justificante/test_repository.py src/aeat/domain/justificante/test_secure_storage_roundtrip.py` (`163 passed`).
- `uv run pytest -q src/aeat/domain/portals/test_metadata.py src/aeat/domain/manuals/test_loader.py src/aeat/domain/manuals/test_schema.py src/aeat/domain/manuals/test_fetch.py src/aeat/domain/manuals/test_verify.py` (`54 passed`).
- `uv run pytest -q src/aeat/core/test_external_constants.py src/aeat/core/observability/test_store_redaction.py src/aeat/core/observability/test_sink_redaction.py src/aeat/test_except_clause_narrowing.py src/aeat/application/workflow/test_models.py src/aeat/adapters/persistence/storage/sql/test_constraints.py src/aeat/adapters/persistence/storage/sql/test_records.py src/aeat/adapters/persistence/storage/sql/test_repository.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py` (`123 passed`).
- `uv run pytest -q src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_expedientes.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/auth/test_diagnostics.py src/aeat/application/user_profile/test_censo_sync.py src/aeat/application/filing/test_import.py src/aeat/application/filing/reconciliation/test_reconcile.py` (`79 passed`).
- `uv run pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` (`93 passed`).
- `uv run pytest -q src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_modelo_151_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_210_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_714_stub_refusal.py src/aeat/entrypoints/cli/test_modelo_721_stub_refusal.py src/aeat/entrypoints/cli/test_registry_cli.py` (`80 passed`).
- `uv run pytest -q src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` (`37 passed`).
- `uv run pytest -q src/aeat/application/workflow/test_engine.py` (`46 passed`).

## Notes

No live AEAT request was made. No filing, payment, confirmation, represented-taxpayer selection, or remote write path was executed.

During broader verification, `src/aeat/domain/calculations/registry/test_modelo_100_registry.py::test_modelo_100_payments_retentions_construct_excludes_atribucion_bindings` failed in the pre-existing registry expectation path with an extra expected binding `renta-2025-base-liquidable-negativa-general-anterior`. This is not caused by the URL migration and is queued in the audit as follow-up.
