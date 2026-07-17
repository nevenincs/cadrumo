---
tags:
  - '#exec'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-plan]]"
---

# Add the allowlist-length and per-class count ratchet so an increase requires editing the declaration in the same commit while a decrease is free

## Scope

- `src/aeat/tests/test_lazy_import_policy.py`

## Description

- Add the length and per-class count ratchet: `_ALLOWLIST_EDGE_CEILING` (655) pins the declared edge total, `_SITE_CEILINGS` pins each class's baseline site count, and `test_unsanctioned_site_count_ratchet` asserts live per-class site counts and the live edge total stay at or below their ceilings.
- Add `test_declared_allowlist_is_internally_consistent` pinning the declared edge total to the ceiling and forbidding an edge filed under two classes.

## Outcome

An increase (a new import beyond the ceiling) fails until the ceiling is raised in the same commit; a decrease passes freely. Verified by probe: a throwaway module with one unsanctioned import failed the edge-subset gate (naming the site path and the five sanctioned classes) and the ratchet, then passed once removed. All five module tests green; ruff clean.

## Notes

Per-class SITE ceilings catch a new site added on an already-allowlisted edge (which the edge-subset gate alone would miss); the two gates together cover both new couplings and new sites on existing couplings.
