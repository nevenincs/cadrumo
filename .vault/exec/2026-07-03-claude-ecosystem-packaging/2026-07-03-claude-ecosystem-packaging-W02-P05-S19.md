---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:a9cf500ba5a3d1645e3b9dfc7b66c1773f423ef93ddc64c64a75662f95a2a01b'
step_id: 'S19'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add an anti-tautology test that an absent companion binary surfaces a loud advisory and is never silently accepted

## Scope

- `src/aeat/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`

## Description

- Add the anti-tautology proof that an absent companion binary surfaces the loud advisory (naming the file and the install hint) and is NEVER silently accepted, and that a non-companion absence still raises.
- Commit `9754913bf2`.

## Outcome

- The advisory path is proven loud; silent degradation is structurally excluded.

## Notes

Record authored by the coordinator from the verified commit at HEAD; gate re-verified post-hoc (companion test module 5 passed).
