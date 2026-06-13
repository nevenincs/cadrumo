---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S53'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W09.P26.S53`

Added regression tests for the W09 warning-sidecar guards and their legal
boundaries.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W09-P26-S53.md`

## Description

The tests prove same-basket Anexo C carryforward states and same-branch
deferred-imputation slots do not warn as typo twins. They also prove Anexo C
baskets, deferred branches, gain/loss polarity, and cadastral reference versus
flag roles are not treated as axis siblings.

## Tests

`uv run ruff check src/aeat/domain/calculations/registry/_validate_semantic_roles.py src/aeat/domain/calculations/registry/test_semantic_role.py`

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
