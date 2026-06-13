---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S67'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W13.P34.S67`

Marked source-grounded Modelo 200 legal-reference singleton roles explicitly
instead of relying on generic legal-marker suppression.

- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0253-deducciones-doble-imposicion-internacional-rdleg-4-di-internacional-2008.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0758-operaciones-a-plazos-art-11-4-lis-aumento.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0759-operaciones-a-plazos-art-11-4-lis-disminucion.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0940-operaciones-a-plazos-dt-1a-lis-aumento.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/casillas/0941-operaciones-a-plazos-dt-1a-lis-disminucion.toml`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W13-P34-S67.md`

## Description

The affected `art. 11.4 LIS`, `DT 1a LIS`, and `RDLeg. 4/2004` rows now carry
`semantic_role_cardinality = "intentional_singleton"` and a reason tied to the
source-visible legal-reference identity. This keeps the warning surface clean
without teaching the validator to normalize legal markers generically.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_modelo_200_registry.py src/aeat/domain/calculations/registry/test_committed_registry.py -q`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py src/aeat/domain/calculations/registry/test_cross_revision_drift.py::test_singleton_semantic_role_warning_count_does_not_regress -q`
