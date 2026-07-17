---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add an anti-tautology test that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate

## Scope

- `src/aeat/domain/calculations/registry/tests/test_corpus_catalogue_companion.py`

## Description

- Add the anti-tautology proof that a corrupted PRESENT corpus binary still hard-fails the byte-exact hash gate: copy a real cited binary to a temp source root, flip bytes, assert `RegistryValidationError`.
- Commit `1a9a6802a7`.

## Outcome

- The companion-aware branch cannot weaken present-binary integrity: corruption is proven to still fail loudly.

## Notes

Record authored by the coordinator from the verified commit at HEAD; gate re-verified post-hoc (companion test module 5 passed).
