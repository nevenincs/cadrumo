---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S374'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S374 - Close AFR-272 for CLI bootstrap custody

Scope: close `AFR-272` for `src/aeat/entrypoints/cli/__init__.py` with signals
`active-profile, manifest-bucket, master-key, sql-route, plain-file`, target
`bootstrap-custody`, and owner `W12.P22.S89`.

## Description

- Audited the root CLI package for deprecated `config init` exposure, direct storage
  repository construction, active-profile normalization, bootstrap exemptions,
  master-key session activation, SQL-route write guards, and plain-file reads.
- Confirmed the command tree is lazily assembled and does not mount a deprecated
  `config init` command.
- Confirmed root dispatch resolves `--profile` and `AEAT_ACTIVE_PROFILE` labels to UUID
  bucket ids before storage route resolution.
- Confirmed non-exempt subcommands pass through `inspect_storage_write_policy` and
  active bucket-session activation before encrypted profile-bound work.
- Replaced the deprecated Click `protected_args` property read with a `ctx.args` first
  path and an internal Click 8 compatibility fallback, removing the runtime
  deprecation warning without weakening bootstrap path reconstruction.
- Fixed import formatting in `test_active_profile_env_override_name.py` so the focused
  S374 ruff gate covers the root CLI tests cleanly.
- Closed `W12.P26.S374` through `vaultspec-core vault plan step check` and updated
  the `AFR-272` register status to `closed`.

## Outcome

`AFR-272` is closed. `entrypoints/cli/__init__.py` is the intended bootstrap-custody
gate, not a duplicate storage repository. The root callback keeps help/version/bare
surfaces state-light, opens bucket sessions only for non-exempt subcommands, and keeps
profile-bound write routing behind the centralized storage write policy.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/_bootstrap_exempt.py src/aeat/application/storage_write_policy.py src/aeat/entrypoints/cli/tests/test_retired_cli_literals.py src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/tests/test_active_profile_env_override_name.py src/aeat/entrypoints/cli/tests/test_cold_start_no_profile.py src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`
- `uv run --no-sync pytest -q -m integration -W error::DeprecationWarning:aeat.entrypoints.cli.__init__ src/aeat/entrypoints/cli/tests/test_retired_cli_literals.py src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py src/aeat/entrypoints/cli/tests/test_active_profile_env_override_name.py src/aeat/entrypoints/cli/tests/test_cold_start_no_profile.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

A broad `PYTHONWARNINGS=error::DeprecationWarning` run is blocked before tests start by
a `pytest-asyncio` configuration deprecation. The final pytest gate scopes the warning
error to `aeat.entrypoints.cli.__init__`, which is the S374 code path under review.
