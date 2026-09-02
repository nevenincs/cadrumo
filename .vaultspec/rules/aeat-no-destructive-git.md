---
name: aeat-no-destructive-git
---

# No destructive git commands

## Absolute prohibition

Never run a git command that can discard, rewrite, or relocate work that is not
yours to move. These are forbidden outright, with no exception and no "safe"
variant:

- `git stash` in every form, including `push`, `pop`, `apply`, `drop`, `clear`,
  and `save`. Stashing removes another contributor's in-flight edits from the
  working tree, and popping against a moved `HEAD` writes conflict markers into
  source files.
- `git reset` (`--hard`, `--mixed`, `--soft`), `git restore`, and
  `git checkout -- <path>` used to discard working-tree or index changes.
- `git clean` in every form.
- `git rebase`, `git cherry-pick`, `git revert`, `git commit --amend`, and any
  history rewrite (`filter-branch`, `filter-repo`, `push --force`).
- `git branch -D`, `git worktree remove --force` on a worktree you did not
  create, and any deletion of a ref you do not own.
- Removing or bypassing a lock file such as `.git/index.lock`. A held lock means
  another process is mid-operation; wait, or report it.

## Why

A dirty worktree is another contributor's work in progress, and this repository
is edited concurrently. A stash/pop cycle in one session removed a contributor's
uncommitted edits and, on restore against an advanced `HEAD`, wrote
`<<<<<<<`/`=======`/`>>>>>>>` markers into nine tracked source files, breaking
every module that imported them. Nothing warned before the damage; the loss was
found only by a later import smoke test. No reversibility argument survives
that: the operations above destroy state that exists nowhere else.

## Instead

- To read a committed version, use a read-only command that writes nothing:
  `git show HEAD:<path>`, `git diff`, `git log`, `git cat-file`.
- To compare against a baseline, create a separate worktree
  (`git worktree add --detach <dir> HEAD`) and read from it. Never mutate the
  working tree to get a clean state.
- To test whether a local edit causes a failure, copy the file aside and restore
  it by copy, or evaluate the question from `git diff` output.
- If work genuinely must be set aside, stop and ask the operator. Removing
  someone's uncommitted changes is their decision, never the agent's.

## Scope

This binds every agent and every session, including when a command appears to
target only files the agent itself wrote: a path-scoped destructive command
still acts on whatever the working tree holds at that moment, which may have
changed. Commit, push, merge, and any other command that alters shared or
external state still require an explicit operator request.
