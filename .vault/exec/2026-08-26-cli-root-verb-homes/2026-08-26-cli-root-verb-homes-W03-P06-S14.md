---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:0e531ce2d6fe06d339468f89c2e5f9d6c67b327864ec0424a5d7dfe48907175c'
step_id: 'S14'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Rename config profile restore to config profile archive import

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_restore_cli.py`
- `M` `src/cadrumo/entrypoints/cli/_config_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_authentication_contract.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_profile_restore_cli.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `dev.locales scaffold --check` -> `pass`
