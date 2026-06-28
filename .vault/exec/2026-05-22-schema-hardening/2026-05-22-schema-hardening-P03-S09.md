---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S09'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P03.S09`

Added regression coverage for the approved `sin` boundary and the committed
singleton metadata.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S09.md`

## Description

The tests now assert that unmarked `con`/`sin` maintenance-employment roles are
not axis siblings and should warn, while the reviewed committed rows must carry
explicit singleton metadata and stay warning-clean after registry load.

## Tests

Covered by the P03.S10 gate record.
