---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:5bf125f04fc08a19075fd9253a648663588de477b343cdd0c6db47343326d86f'
step_id: 'S127'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Remove the shipped authentication-provider implementation ledger and future reserved slots, deriving the operator catalogue only from the executable AuthProviderKind authority

## Scope

- `authentication catalogue`
- `operator errors`
- `CLI auth rendering`
- `tests`
- `and locale contracts`

## Changes

- `M` `src/cadrumo/application/auth/catalogue.py`
- `M` `src/cadrumo/application/auth/operator.py`
- `M` `src/cadrumo/application/auth/operator_cleanup.py`
- `M` `src/cadrumo/application/auth/operator_results.py`
- `M` `src/cadrumo/application/auth/tests/test_catalogue.py`
- `M` `src/cadrumo/application/auth/tests/test_operator.py`
- `M` `src/cadrumo/application/auth/tests/test_operator_storage_session.py`
- `M` `src/cadrumo/application/user_profile/tests/test_first_run_config_cli_surface.py`
- `M` `src/cadrumo/core/errors/registry/_application_part1.py`
- `M` `src/cadrumo/core/tests/test_locale_coverage_hardened_errors.py`
- `M` `src/cadrumo/entrypoints/cli/config/_auth.py`
- `M` `src/cadrumo/entrypoints/cli/config_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py`
- `M` `src/cadrumo/locales/_intentional_identical.json`
- `M` `src/cadrumo/locales/ca/application.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/en/application.yml`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/application.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/hu/application.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/auth/tests/test_catalogue.py src/cadrumo/application/auth/tests/test_operator.py::test_configure_operator_auth_unknown_provider_emits_no_event src/cadrumo/entrypoints/cli/tests/test_workflow_surface.py::test_config_auth_accepts_supported_provider_and_rejects_others src/cadrumo/application/user_profile/tests/test_first_run_config_cli_surface.py::test_setup_auth_rejects_unsupported_provider src/cadrumo/core/tests/test_locale_coverage_hardened_errors.py` -> `pass`
- `verify:` `uv run --no-sync ruff check ...` -> `pass`

## Notes

The locale parity gate contains no residue from this change. It remains red only because all four catalogues lack the peer-owned live key `tui.declarations.lifecycle.verification_refused`.
