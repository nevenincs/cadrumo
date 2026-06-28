---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W01.P002'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-init-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-config-auth-shape-adr]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-overview-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `cli-workflow-redesign` exec: W01.P002 shadow duplicate removal

## Scope

Closed plan rows:

- `W01.P002.S0007`
- `W01.P002.S0008`
- `W01.P002.S0009`
- `W01.P002.S0010`
- `W01.P002.S0011`
- `W01.P002.S0012`

## Changes

- Renamed the setup-named backend reset branch to `aeat.application.config_reset` and rewired `aeat config reset` to call `reset_config`.
- Mounted the accepted `aeat config init` wizard command and removed the runtime `aeat config setup` alias.
- Mounted grouped `aeat config profile ...`, `aeat config auth ...`, and `aeat config doctor connectivity` commands so guidance points at exposed surfaces.
- Moved `config auth` command behavior behind `aeat.application.auth._operator` so the CLI only parses transport arguments and delegates provider catalogue, configure, status, test, and clear operations to the backend service.
- Updated application-owned auth recovery guidance from removed `setup auth login/status` routes to accepted `config auth test/status/clear/configure` language.
- Updated profile, overview, diagnostics, wizard, filing, topic, archive, and review guidance to accepted `config init`, `config profile`, `config bucket`, `app overview`, `app ledger`, `app modelo`, `app review`, and `app registry` surfaces.
- Added the read-only `aeat app review queue/show` surface backed by `aeat.application.review._operator`, with accepted source-kind vocabulary and rendered operator summaries.
- Updated review queue drill commands so application items no longer point to retired `financial`, `filing`, or top-level `review` roots.
- Added `test_w01_p002_operator_guidance_uses_accepted_roots` in the CLI boundary inventory to guard the cleaned guidance surface from reintroducing retired roots.
- Remediated the mandatory code-review blockers: `app review show` is now mounted, auth business behavior is in an application service, reserved auth provider slots are listed, stale auth guidance is guarded, and flat `config list/get/set/unset/status` aliases are removed.
- Removed the retired `aeat app invoice`, `aeat app declaration`, `aeat app archive`, and `aeat app topic` mini-app mounts so the app root exposes only the accepted workflow surfaces.
- Hardened `aeat app review queue` with the accepted `--source-kind` filter, reserved fail-closed source kinds, and row fields for source kind, affected object id, bucket id, and period.
- Extended workflow state with bucket event history fields and made auth configure/clear mutations append bucket-scoped auth events.
- Changed `config auth test` to consult the selected provider backend description instead of projecting stored auth state only.
- Normalized retained config/profile/auth output through `_emit` and converted CLI-local validation refusals to central typed errors.
- Replaced the stale `aeat app archive export/import` CLI smoke tests with a retired-surface regression so active tests no longer encode the rejected archive mini-app.
- Replaced stale active CLI surface tests for `aeat app invoice` and `aeat app declaration` with retired-surface regressions and accepted app help expectations.
- Fixed application review model rehydration for persisted workflow review records so strict pydantic records parse JSON-restored decimals, datetimes, event history, and split metadata on read paths.

## Modified Paths

- `src/aeat/application/config_reset.py`
- `src/aeat/application/test_config_reset.py`
- `src/aeat/application/auth/_operator.py`
- `src/aeat/application/auth/_acquisition_lock.py`
- `src/aeat/application/auth/_catalogue.py`
- `src/aeat/application/auth/_sessions.py`
- `src/aeat/application/auth/__init__.py`
- `src/aeat/application/diagnostics.py`
- `src/aeat/application/filing/_calculate.py`
- `src/aeat/application/filing/_export.py`
- `src/aeat/application/operator_surface/_contract.py`
- `src/aeat/application/overview/__init__.py`
- `src/aeat/application/overview/test_calendar.py`
- `src/aeat/application/profile/__init__.py`
- `src/aeat/application/review/_adapters.py`
- `src/aeat/application/review/_operator.py`
- `src/aeat/application/review/_edit.py`
- `src/aeat/application/review/_filter.py`
- `src/aeat/application/review/test_adapters.py`
- `src/aeat/application/review/test_models.py`
- `src/aeat/application/topics/__init__.py`
- `src/aeat/application/wizard/_commands.py`
- `src/aeat/application/wizard/_status.py`
- `src/aeat/application/wizard/test_status.py`
- `src/aeat/application/wizard/test_status_next_action.py`
- `src/aeat/application/test_diagnostics_dispatch.py`
- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/entrypoints/cli/_config.py`
- `src/aeat/entrypoints/cli/_review.py`
- `src/aeat/entrypoints/cli/__init__.py`
- `src/aeat/entrypoints/cli/test_backend_boundary.py`
- `src/aeat/entrypoints/cli/test_workflow_surface.py`
- `src/aeat/core/config.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/hu.yml`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Verification

- `uv run --no-sync ruff check ...` on modified Python files: passed.
- `uv run --no-sync python -m compileall -q ...` on modified Python files: passed.
- `uv run --no-sync aeat config init --help`: passed.
- `uv run --no-sync aeat config setup --help`: failed as expected with no such command.
- `uv run --no-sync aeat config auth --help`: passed and listed `providers`, `configure`, `status`, `test`, and `clear`.
- `uv run --no-sync aeat config profile --help`: passed.
- `uv run --no-sync aeat config doctor connectivity --help`: passed.
- `uv run --no-sync aeat config auth providers`: passed and listed implemented `certificate`/`clave_movil` plus reserved `clave_pin`/`clave_permanente`/`dnie_pkcs`.
- `uv run --no-sync aeat app review --help`: passed.
- `uv run --no-sync aeat --format json app review queue`: passed and emitted rendered operator summaries.
- `uv run --no-sync aeat app invoice --help`: failed as expected with no such command.
- `uv run --no-sync aeat app declaration --help`: failed as expected with no such command.
- `uv run --no-sync aeat app archive --help`: failed as expected with no such command.
- `uv run --no-sync aeat app topic --help`: failed as expected with no such command.
- `uv run --no-sync aeat app review queue --source-kind ledger_transaction`: passed and rendered source kind, affected object, bucket, and period columns.
- `uv run --no-sync aeat --format json config auth test --provider certificate`: passed and reported certificate backend readiness from provider description.
- `uv run --no-sync aeat --format json config auth status`: passed through the normalized JSON emitter.
- `uv run --no-sync aeat config set --help`: failed as expected with no such command.
- `uv run --no-sync aeat config profile --help`: passed.
- `uv run --no-sync python -m pytest src/aeat/application/test_config_reset.py src/aeat/application/auth/test_catalogue.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/overview/test_calendar.py src/aeat/application/review/test_models.py src/aeat/application/review/test_adapters.py src/aeat/application/test_diagnostics_dispatch.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_backend_boundary.py::test_w01_p002_operator_guidance_uses_accepted_roots src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_surface_uses_singular_user_domains src/aeat/entrypoints/cli/test_workflow_surface.py::test_removed_developer_commands_are_not_registered src/aeat/entrypoints/cli/test_workflow_surface.py::test_root_no_args_renders_help_successfully src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_auth_accepts_supported_provider_and_rejects_others src/aeat/entrypoints/cli/test_workflow_surface.py::test_user_help_surfaces_do_not_leak_translation_keys src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_review_queue_accepts_source_kind_filter src/aeat/entrypoints/cli/test_config_setter.py src/aeat/application/test_config_parity.py -q`: 129 passed.
- `uv run --no-sync python -m pytest src/aeat/entrypoints/cli/test_archive_cli.py -q`: 1 passed.
- `uv run --no-sync python -m pytest src/aeat/application/test_config_reset.py src/aeat/application/auth/test_catalogue.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/overview/test_calendar.py src/aeat/application/review/test_models.py src/aeat/application/review/test_adapters.py src/aeat/application/test_diagnostics_dispatch.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_backend_boundary.py::test_w01_p002_operator_guidance_uses_accepted_roots src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_surface_uses_singular_user_domains src/aeat/entrypoints/cli/test_workflow_surface.py::test_removed_developer_commands_are_not_registered src/aeat/entrypoints/cli/test_workflow_surface.py::test_root_no_args_renders_help_successfully src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_auth_accepts_supported_provider_and_rejects_others src/aeat/entrypoints/cli/test_workflow_surface.py::test_user_help_surfaces_do_not_leak_translation_keys src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_review_queue_accepts_source_kind_filter src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_archive_cli.py src/aeat/application/test_config_parity.py -q`: 130 passed.
- `uv run --no-sync python -m pytest src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/review/test_models.py -q`: 18 passed.
- `uv run --no-sync python -m pytest src/aeat/application/test_config_reset.py src/aeat/application/auth/test_catalogue.py src/aeat/application/auth/test_ensure_session.py src/aeat/application/overview/test_calendar.py src/aeat/application/review/test_models.py src/aeat/application/review/test_adapters.py src/aeat/application/test_diagnostics_dispatch.py src/aeat/application/wizard/test_status.py src/aeat/application/wizard/test_status_next_action.py src/aeat/application/operator_surface/test_contract.py src/aeat/entrypoints/cli/test_backend_boundary.py::test_w01_p002_operator_guidance_uses_accepted_roots src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_surface_uses_singular_user_domains src/aeat/entrypoints/cli/test_workflow_surface.py::test_removed_developer_commands_are_not_registered src/aeat/entrypoints/cli/test_workflow_surface.py::test_root_no_args_renders_help_successfully src/aeat/entrypoints/cli/test_workflow_surface.py::test_config_auth_accepts_supported_provider_and_rejects_others src/aeat/entrypoints/cli/test_workflow_surface.py::test_user_help_surfaces_do_not_leak_translation_keys src/aeat/entrypoints/cli/test_workflow_surface.py::test_app_review_queue_accepts_source_kind_filter src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_archive_cli.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/test_config_parity.py -q`: 142 passed.

## Notes

`uv run --no-sync pytest ...` through the console-script entrypoint initially reported a stale error-code registry import for the renamed config reset error. Running the same test selection through `uv run --no-sync python -m pytest ...` loaded the current source registry and passed.

`uv run --no-sync python -m pytest src/aeat/locales/test_parity.py src/aeat/application/wizard/test_wizard_translations_resolve.py -q` passed wizard translation resolution and failed `test_codebase_to_locale_parity` because each locale contains the existing broader extra-key corpus.
