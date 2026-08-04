---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:0f4b03bce015dc630d29ebae91c5a2a4e9a358b84bd4741ecb975b2978786e66'
step_id: 'S02'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Declare ExternalPathRole as a StrEnum carrying the four escape roles plus OPERATOR_DIRECTED_OUTPUT, gated by a test asserting the five members and rejecting an undeclared role string

## Scope

- `src/cadrumo/core/_storage_taxonomy.py`

## Description

- Declare `ExternalPathRole` as a StrEnum carrying five members: the four escape roles plus `OPERATOR_DIRECTED_OUTPUT`.

## Outcome

Landed in commit `08c61859c0`, already carrying all five members at first landing — `OPERATOR_DIRECTED_OUTPUT` (ADR R17's correction on re-checking R6's escape test against a real field) was not a later follow-up commit; the correction evidently happened before this commit was authored, not after. Gated by `test_external_path_role_carries_the_five_escape_roles` and `test_an_undeclared_escape_role_is_not_a_member`.

## Notes
