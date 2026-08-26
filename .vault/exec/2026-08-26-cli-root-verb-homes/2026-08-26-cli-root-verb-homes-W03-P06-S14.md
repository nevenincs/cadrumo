---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:dfb80efd8c848088279f0858a1d8aafc2749e4ab76f86c11f33e41541b8d9944'
step_id: 'S14'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
