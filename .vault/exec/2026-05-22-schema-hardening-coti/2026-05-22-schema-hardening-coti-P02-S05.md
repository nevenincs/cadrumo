---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S05'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---



# `schema-hardening-coti` `P02.S05`

Added `coti` boundary and committed singleton regression tests.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P02-S05.md`

## Description

Tests now prove that unmarked `coti` roles are not axis siblings and should
warn, while the committed source-reviewed `gp_fondos_coti` rows are explicitly
marked and warning-clean.

## Tests

Covered by P03.S06 gate results.
