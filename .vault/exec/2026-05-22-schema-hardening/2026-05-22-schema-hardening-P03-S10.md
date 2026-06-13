---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S10'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P03.S10`

Ran semantic-role warning corpus gates and targeted registry validation.

- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S10.md`

## Description

The focused semantic-role suite, ruff check, cross-revision singleton drift
gate, Modelo 200 registry tests, committed registry tests, and direct M100/M200
warning probe all passed after the `sin` burn-down.

## Tests

`uv run pytest src/aeat/domain/calculations/registry/test_semantic_role.py -q`
passed with 43 tests. `uv run ruff check` passed for the touched validator and
semantic-role test file. `uv run pytest` for the drift, Modelo 200 registry,
and committed registry targets passed with 49 tests. The direct committed
Modelo 100 and Modelo 200 warning probe returned 0 warnings.
