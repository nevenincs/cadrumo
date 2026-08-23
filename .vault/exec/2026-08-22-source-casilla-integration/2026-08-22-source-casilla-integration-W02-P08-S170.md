---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:38f749c951f9fd50c95ed1732b7ff1dfd765b91aa72f8c9da1f041cbfb4f942d'
step_id: 'S170'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# add typed row-source identity coordinates to the canonical source-resolution carrier and collision merge

## Scope

- `src/cadrumo/application/aggregation/_source_mesh.py`

## Description

- Add a strict generic row-source identity member carrying source kind, opaque stable identity, and canonical content fingerprint.
- Bind identity members to existing 1-based row-value coordinates with deterministic ordering and orphan refusal.
- Preserve independently migrated row producers while making identity-bearing coordinates collision-exclusive in both merge modes.
- Exclude raw source-row identities from ordinary representation and generic serialization while retaining the typed runtime attribute for encrypted persistence.
- Add focused mutation, confidentiality, M720 coexistence, and equal-value collision tests.

## Outcome

The source-resolution carrier now retains a frozen row-source identity map keyed by the same `(BindingId, row_index)` coordinate as `row_binding_values`. Each member carries the canonical source kind, an opaque bounded identity, and a canonical content digest. Identity coordinates without corresponding row values fail closed, indexes remain 1-based, and both maps are ordered deterministically.

Existing M720 rows remain valid without identities until their separately adjudicated migration. An identity-bearing coordinate cannot be claimed twice in either the exclusive mesh or precedence overlay, even when the second value is identical. Raw identities are excluded from generic dumps, JSON, representations, validation errors, and collision diagnostics; S171 owns their explicit encrypted persistence.

Independent review reported zero findings after one documentation correction. Forty-six focused source-mesh tests passed, and Ruff and the focused type checker were clean.

## Notes

The initial exact-bijection interpretation was narrowed under the approved migration ruling: the generic carrier enforces identity-key subset and no orphan, while S176 owns complete inventory cohort bijection. A concurrent shared commit captured the first portion of the implementation before final remediation; the final scoped commit records the remaining contract hardening and lifecycle evidence.

A broader M720 run passed 61 tests and failed three existing assertions because foreign-asset provenance was empty. Row values remained correct and the failures did not involve row identities or this diff; the unrelated provenance behavior was left untouched.
