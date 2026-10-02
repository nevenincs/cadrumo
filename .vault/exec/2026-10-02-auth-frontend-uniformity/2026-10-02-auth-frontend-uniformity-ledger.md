---
tags:
  - '#exec'
  - '#auth-frontend-uniformity'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:30361c4148b8a8f652418d03dee1b220ba0b9bba68a9774b66277b4ebcafd8d6'
related:
  - "[[2026-10-02-auth-frontend-uniformity-plan]]"
---

# `auth-frontend-uniformity` ledger

## Changes

- `S01` `A` `src/cadrumo/application/auth/preferences.py`
- `S01` `A` `src/cadrumo/application/auth/tests/test_profile_configuration.py`
- `S01` `M` `src/cadrumo/application/auth/operator.py`
- `S01` `M` `src/cadrumo/application/auth/credentials.py`
- `S01` `M` `src/cadrumo/application/auth/operator_results.py`
- `S01` `M` `src/cadrumo/application/auth/operator_result_projections.py`
- `S01` `M` `src/cadrumo/application/user_profile/fact_write.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_fact_write_door_contract.py`
- `S01` `verify:` `auth application and CLI contracts pytest -m unit or integration (188 tests)` -> `pass`
- `S01` `verify:` `scoped Ruff lint and format` -> `pass`
- `S01` `verify:` `scoped ty` -> `pass`
- `S01` `by:` `Codex`
- `S02` `A` `src/cadrumo/application/auth/configuration_result.py`
- `S02` `A` `src/cadrumo/application/auth/configuration_submission.py`
- `S02` `A` `src/cadrumo/entrypoints/auth_configuration.py`
- `S02` `A` `src/cadrumo/entrypoints/tui/tests/test_auth_frontend_uniformity.py`
- `S02` `M` `src/cadrumo/application/auth/operation_definitions.py`
- `S02` `M` `src/cadrumo/application/auth/operator_result_projections.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_auth.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_auth_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_auth_configure_identity_projection.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `verify:` `owning auth and actual CLI/TUI integration plus CLI architecture and profile admission tests (unit or integration; 219 passed)` -> `pass`
- `S02` `verify:` `scoped Ruff lint and format (12 paths)` -> `pass`
- `S02` `verify:` `scoped ty (12 paths)` -> `pass`
- `S02` `by:` `Codex`
- `S02` `M` `src/cadrumo/application/auth/configuration_submission.py`
- `S02` `M` `src/cadrumo/entrypoints/auth_configuration.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/tests/test_auth_frontend_uniformity.py`
- `S02` `M` `src/cadrumo/core/errors/hierarchy.py`
- `S02` `M` `src/cadrumo/core/errors/error_codes.py`
- `S02` `M` `src/cadrumo/core/errors/registry/_core.py`
- `S02` `A` `src/cadrumo/core/errors/tests/test_public_error_projection.py`
- `S02` `A` `.vault/audit/2026-10-02-auth-frontend-uniformity-audit.md`
- `S02` `verify:` `core error contracts and frontend auth integration (61 passing; one profile-switch verification fixture corrected)` -> `pass`
- `S02` `verify:` `corrected profile-switch refusal test (20261002T082549.846008Z-pytest-90368-1642040d; 1 passed)` -> `pass`
- `S02` `verify:` `scoped Ruff lint and format (9 paths)` -> `pass`
- `S02` `verify:` `scoped ty (9 paths)` -> `pass`

## Notes

- `S02` CLI and installed TUI auth selection use the same registered request, public observation, result projector and failure metadata. TUI reuses its running graph. Repeated configuration reports NONE effect. Safe public result omits paths, identities and localized prose. New CLI route option uses the same closed schema. Sensitive typed inputs are masked. Test log 20261002T080150.404448Z-pytest-79772-2965d6ec.
- `S02` Integrated review reopened S02 for exact displayed-profile subject binding and preserving the public failure taxonomy. Both corrected. The preceding 62-test run had 61 passing and one failure only in reading the original profile after a switch; that test now reauthenticates before checking unchanged facts and passed separately. Core error registry/envelope/inventory checks remain applicable and passed. Public failure code/category/retryability/runbook are retained, with only validated opaque diagnostic references.
