# AEAT git and worktree safety — ABSOLUTE PROHIBITION

This worktree runs many concurrent agents from independent campaigns holding
uncommitted work in the index and working tree at all times. Any destructive Git
operation can silently destroy a peer agent's hours of in-flight work. **The
commands below are categorically forbidden — there are no debugging exceptions,
no "I'll pop it back" exceptions, no "just to isolate the failure" exceptions.**

## Forbidden commands

- `git stash` in any form (`push`, `pop`, `apply`, `drop`, `save`, `store`,
  `clear`, `create`, or bare). Stash captures every concurrent campaign's WIP
  into one blob; pop conflicts partially apply and strand peer work.
- `git reset` in any form, including with a `<paths>` pathspec.
- `git checkout <path>` / `git checkout -- <path>` (file restore or discard),
  and `git restore` in any form.
- `git checkout <branch>` / `git switch <branch>`. The worktree is pinned to its
  branch.
- `git clean` in any form.
- `git rebase` in any form, and `git commit --amend` (a peer commit may have
  landed on HEAD since yours).
- `git revert <sha>` against any commit that is not your own from this session.
- `git push --force` / `--force-with-lease`.
- `git worktree remove` / `prune`, and forced branch deletion (`git branch -D`).
- `rm -rf` / `Remove-Item -Recurse -Force` against any tracked path or any
  directory containing tracked paths.
- **Deleting, moving, truncating or renaming anything under `.git/`, including
  `.git/index.lock`.** Diagnose a held lock by its mtime — advancing means
  contention, frozen means the holder died — and report it. Never remove it.

## No exceptions

If you are tempted because *"I just need to isolate whether this failure is mine
or pre-existing"* — **NO.** Investigate by inspection: `git diff -- <files>`,
`git log -- <files>`, run the specific test in isolation. To compare against a
committed version without `checkout` or `stash`, copy the working file aside,
`Write` the `git show HEAD:<file>` bytes in place, test, then restore your copy.

If it is *"I'll pop it right back"*, *"it's just my own files"*, or *"the
pre-tool-use hook will allow it"* — **NO.** You cannot guarantee a peer has not
written into the same file between your stash and your pop.

If you are genuinely blocked and reaching for these tools, **STOP and report**.
"Blocked because I would need to stash" is acceptable; stashing is not.

## Allowed operations

- Read-only: `git status`, `git diff` (any form), `git log` (including `-S`,
  `--grep`, `-- <path>`), `git show <sha>`, `git stash list`, `git ls-files`,
  `git branch --show-current`, `git rev-parse`, `git merge-base`.
- `git add -- <explicit pathspec>` for files you authored. Never `git add -A`,
  `git add .`, or `git add -p`.
- `git commit -- <explicit pathspec>` for files you authored, or a
  verified-index bare commit after an apply-cached staging. Message via `-m` or
  `-F`.
- `git apply --cached` and `git apply --cached --reverse` — the sanctioned way
  to stage and unstage an own-edits-only patch on a contended file.
- `git fetch` (read-only), `git pull --ff-only` on `main` only when authorised.
- `git push` (without `--force`) of your own branch's new commits — after
  checking `git log origin..HEAD`, because a push carries all ancestors
  including a peer's hold-for-now commit.

## Other worktree discipline

Keep worktrees on disk permanently. Do not move, delete, or rewrite another
agent's workspace. Report stale or merged worktrees as inventory only.

Name branches `<type>/<issue>-<subject>` with `feature`, `bug`, or `chore`. Name
worktree folders with the slash flattened to a dash. Provision new worktrees from
main: create the branch, push upstream immediately, sync all dependency groups,
refresh the lockfile, install vaultspec, then return to main.

## Consequences

A forbidden command run by a dispatched agent is logged as a security incident,
escalated to the operator, and that agent's session is treated as compromised —
its output is reviewed for unrelated destructive side effects before any of its
work is trusted.
