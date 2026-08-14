---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e027715a2f6b73b1f970a9c7ebf6cd81d01438c709db27f81e6d06bebe756e8b'
step_id: 'S56'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Canonicalize fixed-master-key fixtures across persistence storage tests

## Scope

- `src/cadrumo/adapters/persistence/storage`

## Description

- Replace three identical storage master-key fixtures with one canonical test-support fixture.
- Import the exact fixture object through the three narrow child conftest boundaries.
- Preserve function scope, non-autouse behavior, fresh 32-byte keys, and subtree-only visibility.
- Refresh the codebase-wide fixture ownership snapshot against the current shared worktree.

## Outcome

The three storage subtrees now discover one canonical `fixed_master_key` fixture without wrappers, aliases, or broad conftest promotion. All 69 representative storage tests pass, repeated invocations return distinct 32-byte values, and an unrelated storage subtree does not discover the fixture.

## Notes

Ruff, fixture identity and visibility checks, focused behavior tests, diff integrity, and independent review passed. The ownership manifest records the current shared working-tree snapshot because concurrent fixture migrations make a clean-commit census differ from the live campaign source set; its TOML structure, ordering, row digest, conservative disposition rule, and 690 unique fixture identities were validated without claiming an isolated repository baseline.
