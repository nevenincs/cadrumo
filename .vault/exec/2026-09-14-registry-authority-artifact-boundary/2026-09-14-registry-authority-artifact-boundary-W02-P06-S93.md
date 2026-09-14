---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:dbf8c872a0211f2a2bf2bf9217f39ab2c7a0e4b846f9231e273de83f539bb30e'
step_id: 'S93'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Migrate the listed category, deadline, authorisation and treaty consumers under the fact-lane ownership list

## Scope

- `src/cadrumo/domain`

## Changes

- `M` `src/cadrumo/domain/categories/spending_category_catalogue.py`
- `M` `src/cadrumo/domain/categories/proportionality_catalogue.py`
- `M` `src/cadrumo/domain/transactions/retencion_facts.py`
- `M` `src/cadrumo/domain/transactions/tipo_actividad_partitions.py`
- `verify:` `checkpoint B focused import census` -> `pass`
