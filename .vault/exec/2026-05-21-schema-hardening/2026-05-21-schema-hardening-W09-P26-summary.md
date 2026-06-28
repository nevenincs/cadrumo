---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W09.P26` summary

Completed the audited M100 axis sibling guard implementation and regression
tests.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W09-P26-S52.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W09-P26-S53.md`

## Description

The validator now has source-grounded warning-sidecar recognition for audited
Anexo C carryforward and deferred-imputation axis patterns, with tests guarding
against basket, branch, polarity, and cadastral overreach.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
