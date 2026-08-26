---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:1a234b59e81207f875be69f5a2c535d987c49322e965b9c9cf04e43719618f00'
step_id: 'S10'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Fold app maintenance reconcile into config repair and retire the family

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `R` `src/cadrumo/entrypoints/cli/_app_maintenance.py` -> `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports.py`
- `R` `src/cadrumo/entrypoints/cli/_app_maintenance_payloads.py` -> `src/cadrumo/entrypoints/cli/_config/_repair_prepared_exports_payloads.py`
- `D` `src/cadrumo/entrypoints/cli/_app_maintenance_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_command_specs.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_repair_command_specs.py`
- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `dev.locales scaffold --check` -> `pass`
- `verify:` `COMMAND_GRAPH rebuild (294 leaves, policy preserved)` -> `pass`
