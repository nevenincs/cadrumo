---
tags:
  - '#exec'
  - '#schema-hardening-coti'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S03'
related:
  - '[[2026-05-22-schema-hardening-coti-plan]]'
---



# `schema-hardening-coti` `P02.S03`

Removed `coti` from broad optional semantic-role token stripping.

- Modified: `src/aeat/domain/calculations/registry/_validate_semantic_roles.py`
- Created: `.vault/exec/2026-05-22-schema-hardening-coti/2026-05-22-schema-hardening-coti-P02-S03.md`

## Description

The validator no longer treats `coti` as a globally optional token for
semantic-role typo-warning comparison. Other optional tokens and numeric
stripping remain unchanged.

## Tests

Covered by P03.S06 gate results.
