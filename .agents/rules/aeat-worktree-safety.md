---
name: aeat-worktree-safety
trigger: always_on
---

# Cooperative Git handling in a shared worktree

## Rule

Preserve peer work by default. Follow explicit operator Git instructions for the named operation, targets, and current worktree state.

## How

- Serialize repository Git writers and wait for hooks and Git LFS.
- `commit everything` authorizes current non-ignored worktree content. Split it by domain. Push only when requested.
- A bare commit consumes the shared index. A pathspec commit consumes named working-tree files. Use an isolated index only for mixed same-file ownership, then verify the committed diff.
- Before pushing, inspect the outgoing commits, ref, and remote target.
- Treat an advancing lock as active. For a stable lock, attribute the exact repository process; stop it only when authorized. Remove the unchanged lock only after that process is gone. Never kill unrelated Git processes.
- Stash, reset, restore, clean, history rewrites, force-pushes, ref deletion, and worktree removal require explicit authorization and exact-target verification.
- Report scoped validation separately. Required release gates still govern releases.

## Why

`2026-08-08-shared-tree-coordination-audit` and `2026-07-24-worktree-commit-attribution-audit` show both hazards: broad commits capture peer work, while absolute prohibitions block authorized delivery.
