---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d1208f48ae17ee2d340e9dda0ed36b4f7ee2a8f5df0c038e3ac501ae86e58326'
step_id: 'S31'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Correct the config and app root help strings in all four catalogues

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `dev.locales scaffold --check` -> `pass`
