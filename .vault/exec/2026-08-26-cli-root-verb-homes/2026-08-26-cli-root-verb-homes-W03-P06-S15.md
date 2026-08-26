---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:14bb187db812e6a5ba950e33b07996a46d266817bc053559ee7a7688ac2d6ffe'
step_id: 'S15'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Move config google sync push to config profile mirror push

## Scope

- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `R` `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports.py` -> `src/cadrumo/entrypoints/cli/_config/_archive_reconcile.py`
- `R` `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports_payloads.py` -> `src/cadrumo/entrypoints/cli/_config/_archive_reconcile_payloads.py`
- `A` `src/cadrumo/entrypoints/cli/_config/_archive_push_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_repair_command_specs.py`
- `M` `src/cadrumo/application/operator_actions/_catalogue.py`
- `R` `src/cadrumo/entrypoints/cli/tests/test_config_repair_prepared_exports.py` -> `src/cadrumo/entrypoints/cli/tests/test_config_profile_archive_reconcile.py`
- `R` `src/cadrumo/entrypoints/cli/tests/test_config_repair_prepared_exports_command_specs.py` -> `src/cadrumo/entrypoints/cli/tests/test_config_profile_archive_reconcile_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_root_cli_action_producer_census.py`
- `M` `.vault/adr/2026-08-26-cli-root-verb-homes-adr.md`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `dev.locales scaffold --check` -> `pass`
- `verify:` `pytest operator_surface/tests + locus + placement gates` -> `pass`

## Notes

The ADR's `mirror` subject was overruled by the operator: the noun is not one a
CLI operator would guess, and `push` beside a working `export`/`import` pair
makes the absent `pull` more visible than a separate subject did. The artifact
difference the split was protecting is carried in the payload layer instead.
With `push` relocated, `config google sync` held one verb and was flattened to
`config google probe`.
