---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S70'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W14.P36.S70`

Inventoried the remaining semantic-role typo-warning sibling helpers and
classified their source-policy boundaries.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Modified: `.vault/reference/2026-05-21-schema-hardening-reference.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W14-P36-S70.md`

## Description

The audit distinguishes exact source-backed helpers from older broad helpers.
The exact helpers are correction suffixes, Anexo C carryforward, deferred
imputation slots, and family-local generated/pending allowlists. The broad
helpers that need further burn-down are `axis_token_group` and
`optional_or_numeric_token_strip`.

## Tests

Inspected `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
and cross-checked existing regression boundaries in
`src/aeat/domain/calculations/registry/test_semantic_role.py`.
