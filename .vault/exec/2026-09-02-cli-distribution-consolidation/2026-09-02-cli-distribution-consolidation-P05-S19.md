---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:ec0bb857313e5d8b298106f49d7ef5e7fd5254f477351b6eede2f0f888bd7d7c'
step_id: 'S19'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Translate the self-test help key across every supported locale

## Scope

- `src/cadrumo/locales/en/cli.yml`

## Changes

M src/cadrumo/locales/en/cli.yml
M src/cadrumo/locales/es/cli.yml
M src/cadrumo/locales/ca/cli.yml
M src/cadrumo/locales/hu/cli.yml

## Notes

Each locale carries a real translation rather than a copy of the source string.
