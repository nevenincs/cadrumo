---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S56'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename manual publish choices, builders, filename guards, and Trusted Publisher expectations

## Scope

- `.github/workflows/publish.yml`

## Description

- Rename manual publish choices and builders to `cadrumo`, `cadrumo-data-manuals`, and `cadrumo-data-official`.
- Build companions from their canonical `packaging/cadrumo_data_*` projects and guard normalized wheel filenames against the selected distribution.
- Keep the slim-wheel corpus leak and PyPI size-cap guards on Cadrumo paths.
- State that all three PyPI projects require their own confirmed Trusted Publisher registration for this workflow and environment.

## Outcome

Manual publishing now selects, builds, validates, and uploads only canonical
Cadrumo distributions. The workflow remains human-dispatched and OIDC-gated,
and it refuses mismatched, oversized, or corpus-leaking artifacts.

## Notes

- `actionlint` passed and the workflow parsed successfully as YAML.
- Structural checks confirmed the three real project names, normalized filename guards, `pypi` environment, `id-token: write`, and Trusted Publishing command.
- Former product distribution, companion, builder-path, and wheel-prefix residue was absent.
