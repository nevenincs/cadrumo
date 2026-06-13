---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S08'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P03.S08`

Implemented the approved Modelo 200 `sin` optional-token burn-down without
registry rewrites.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0782-libertad-de-amortizacion-con-mantenimiento-de-empl-aumento.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0783-libertad-de-amortizacion-con-mantenimiento-de-empl-disminucion.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0784-libertad-de-amortizacion-sin-mantenimiento-de-empl-aumento.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0785-libertad-de-amortizacion-sin-mantenimiento-de-empl-disminucion.toml`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S08.md`

## Description

Removed `sin` from the broad optional-token set and marked the 12 reviewed
Modelo 200 maintenance-employment correction rows as explicit source-backed
singletons. No other optional or numeric token behavior was changed.

## Tests

Covered by the P03.S10 gate record.
