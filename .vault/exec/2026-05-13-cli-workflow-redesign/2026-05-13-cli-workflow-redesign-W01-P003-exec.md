---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
step_id: 'W01.P003'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` `W01.P003`

Closed plan rows:

- `W01.P003.S0013`
- `W01.P003.S0014`
- `W01.P003.S0015`
- `W01.P003.S0016`
- `W01.P003.S0017`
- `W01.P003.S0018`

## Description

W01.P003 removed compatibility shim files that preserved rejected CLI surfaces after the app root was narrowed to accepted children. The deleted transport modules were the unmounted `app archive`, `app declaration`, `app invoice`, and `app topic` Typer groups, plus the old `entrypoints.cli.auth` compatibility registry for `aeat setup auth`.

The phase also removed active tests that preserved the rejected setup/auth surface, converted the import-contract setup test to assert `aeat setup` retirement, and added a backend-boundary guard proving the removed shim files stay absent. Error-code registry entries for deleted `entrypoints.cli.auth._registry` classes were removed so the registry no longer names deleted transport errors.

Stale operator command guidance was updated from retired `setup auth`, `app declaration`, and `app invoice` spellings to accepted `config auth`, `app modelo`, `app ledger`, and `app review` spellings. The sensitive persistence policy no longer tracks deleted CLI files as governed write surfaces.

## Modified Paths

- `src/aeat/entrypoints/cli/_archive.py`
- `src/aeat/entrypoints/cli/_declaration.py`
- `src/aeat/entrypoints/cli/_invoice.py`
- `src/aeat/entrypoints/cli/_topic.py`
- `src/aeat/entrypoints/cli/auth/__init__.py`
- `src/aeat/entrypoints/cli/auth/_registry.py`
- `src/aeat/entrypoints/cli/test_setup_auth_live.py`
- `src/aeat/entrypoints/cli/test_backend_boundary.py`
- `tests/import_contract/application/setup/test_cli.py`
- `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`
- `src/aeat/core/errors/registry/_entrypoints.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/core/errors/registry/_core.py`
- `src/aeat/core/errors/registry/_domain.py`
- `src/aeat/application/filing/_calculate.py`
- `src/aeat/application/filing/_export.py`
- `src/aeat/application/review/_filter.py`
- `src/aeat/application/review/_edit.py`
- `src/aeat/application/auth/_operator.py`
- `src/aeat/domain/deadlines/_recargo.py`
- `src/aeat/domain/deadlines/test_recargo.py`
- `src/aeat/adapters/outbound/aeat/browser/_factory.py`
- `src/aeat/adapters/outbound/aeat/auth/_clave_movil.py`
- `src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`
- `src/aeat/adapters/outbound/aeat/sede/_auth_state.py`
- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- `src/aeat/adapters/outbound/aeat/sede/_notifications.py`
- `src/aeat/adapters/outbound/aeat/sede/_walker.py`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

- `uv run --no-sync ruff check ...`: passed for modified Python files.
- `uv run --no-sync python -m compileall -q ...`: passed for modified Python files.
- `uv run --no-sync aeat setup --help`: failed as expected with no such command.
- `uv run --no-sync aeat app invoice --help`: failed as expected with no such command.
- `uv run --no-sync aeat app declaration --help`: failed as expected with no such command.
- `uv run --no-sync aeat config auth providers`: passed and listed implemented plus reserved providers.
- `uv run --no-sync python -m pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_w01_p003_removed_cli_shim_files_stay_deleted src/aeat/entrypoints/cli/test_workflow_surface.py::test_removed_developer_commands_are_not_registered src/aeat/entrypoints/cli/test_archive_cli.py src/aeat/entrypoints/cli/test_cli_surface.py tests/import_contract/application/setup/test_cli.py src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py src/aeat/domain/deadlines/test_recargo.py src/aeat/application/auth/test_catalogue.py src/aeat/application/auth/test_ensure_session.py -q`: 42 passed.

## Notes

The broad `src/aeat/core/errors/test_registry_enforcement.py::test_every_registered_code_maps_to_exactly_one_error_subclass` check now imports past the auth/workflow circular import after moving workflow model imports out of `application.auth._operator` module import time, then reports an existing wider error-registry surplus-code corpus. The deleted `entrypoints.cli.auth._registry` codes are no longer present in that surplus list.
