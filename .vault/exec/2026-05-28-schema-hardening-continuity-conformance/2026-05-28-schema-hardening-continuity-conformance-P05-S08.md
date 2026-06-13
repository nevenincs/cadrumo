---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S08'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---



# `schema-hardening` `P05.S08`

Tightened the continuity ADR language around strict validation semantics.

- Modified: `.vault/adr/2026-05-27-schema-hardening-casilla-continuity-contract-adr.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p05-s08-review.md`

## Description

Clarified that `continuidad_validation = "strict"` is surface-scoped
strictness for authored continuity surfaces, not a declaration that every
repeated numeric casilla id in a revision pair has been manually reviewed.

The ADR now explicitly separates surface-scoped strictness from a future
corpus-wide completeness gate. It also requires implementation comments that
name the governing ADR decisions.

## Tests

- `uv run --no-sync vaultspec-core vault check frontmatter --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault check body-links --feature schema-hardening`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-28-schema-hardening-continuity-conformance-plan.md`
