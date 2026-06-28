---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P03` summary

Completed the approved `sin` optional-token burn-down and verified the narrowed
warning behavior.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0782-libertad-de-amortizacion-con-mantenimiento-de-empl-aumento.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0783-libertad-de-amortizacion-con-mantenimiento-de-empl-disminucion.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0784-libertad-de-amortizacion-sin-mantenimiento-de-empl-aumento.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0785-libertad-de-amortizacion-sin-mantenimiento-de-empl-disminucion.toml`
- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S08.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S09.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S10.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-summary.md`

## Description

The broad optional-token list no longer treats `sin` as harmless. The source
reviewed Modelo 200 maintenance-employment correction roles are explicit
singletons, so the warning surface remains clean without suppressing a legally
meaningful distinction.

## Tests

Focused semantic-role tests, ruff, cross-revision singleton drift, Modelo 200
registry tests, committed registry tests, and the direct M100/M200 warning probe
all passed.
