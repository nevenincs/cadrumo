---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S52'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W09.P26.S52`

Implemented source-grounded semantic-role axis sibling recognition for the
audited Modelo 100 warning-sidecar patterns.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W09-P26-S52.md`

## Description

The validator now recognizes audited Anexo C carryforward state suffixes only
within preserved Anexo C baskets, and deferred-imputation slot suffixes only
within preserved ordinary, crypto, or inmueble branches and fields. It does
not add a global cadastral-reference rule.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
