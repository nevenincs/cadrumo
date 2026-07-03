---
name: aeat-git-worktree-safety
trigger: always_on
---

# AEAT git and worktree safety — ABSOLUTE PROHIBITION

This worktree runs many concurrent agents from independent campaigns
holding uncommitted work in the index and working tree at all times.
ANY destructive Git operation can silently destroy a peer agent's
hours of in-flight work. **The following commands are categorically
forbidden in every dispatched agent's tool calls — there are no
debugging exceptions, no "I'll pop it back" exceptions, no "just to
isolate the failure" exceptions.**

## FORBIDDEN COMMANDS — DO NOT RUN, EVER

- `git stash` in any form: `push`, `pop`, `apply`, `drop`, `save`,
  `store`, `clear`, `create`, or bare `git stash`. Stash captures
  every concurrent campaign's WIP into a single blob; pop conflicts
  partially apply and silently strand peer work. The previous
  incidents are documented in audit history.
- `git reset` in any form: `--hard`, `--mixed`, `--soft`, `--keep`,
  or with a `<paths>` pathspec. Reset rewrites the index against
  files peer agents are actively staging.
- `git checkout <path>` or `git checkout -- <path>` (file restore /
  discard). Overwrites uncommitted peer work in the working tree.
- `git checkout <branch>` / `git switch <branch>`. The worktree is
  pinned to its branch; switching disturbs every parallel agent.
- `git restore` in any form (the modern alias for the above).
- `git clean` in any form: `-f`, `-fd`, `-fdx`. Deletes peer agents'
  untracked work without confirmation.
- `git rebase`, `git rebase --interactive`, `git rebase --onto`.
- `git revert <sha>` against any commit that is not your own from
  the current session. Reverting peer commits drops their work.
- `git push --force` / `git push --force-with-lease`. Rewrites
  shared history.
- `git worktree remove` / `git worktree prune` / forced branch
  deletion (`git branch -D`). Worktrees are permanent inventory.
- `rm -rf` / `Remove-Item -Recurse -Force` against any tracked path
  or any directory containing tracked paths.

## ABSOLUTE PROHIBITION — NO EXCEPTIONS

If you are tempted to use one of the above because:

- "I just need to isolate whether this failure is mine or pre-existing"
  — **NO.** Investigate by inspection: read `git diff -- <files>`,
  read `git log -- <files>`, run pytest on the specific test in
  isolation. To compare against a committed version without `checkout`
  or `stash`: copy the working file aside, `git show HEAD:<file>` and
  `Write` the committed content in place, test, then restore your copy.
  Never destroy state to debug.
- "I'll pop it right back" — **NO.** Pop can conflict; partial apply
  strands work. Two consecutive prior incidents confirm this is not
  recoverable in practice.
- "It's just my own files" — **NO.** You cannot guarantee a peer
  agent has not written into the same file in the working tree
  between your stash and your pop.
- "The pre-tool-use will allow it" — **NO.** Any agent that runs a
  forbidden command commits a critical safety violation that gets
  reported back to the coordinator and the user.

If you find yourself genuinely blocked and reaching for these tools,
**STOP and report**. The coordinator will adjudicate. Reporting
"blocked because I would need to stash" is acceptable; running
`git stash` is not.

## ALLOWED OPERATIONS

- `git status`, `git status --short`, `git diff`, `git diff -- <paths>`,
  `git diff --stat`, `git diff --cached`, `git log`, `git log --oneline`,
  `git log -S <symbol>`, `git log -- <path>`, `git show <sha>`,
  `git stash list` (read-only view, NOT mutating), `git ls-files`,
  `git branch --show-current`, `git rev-parse`.
- `git add -- <explicit pathspec>` for files you authored. Never
  `git add -A`, never `git add .`, never `git add -p` (interactive).
- `git commit -- <explicit pathspec>` for files you authored. The
  message via `-m` or `-F message.file`.
- `git fetch` (read-only network operation), `git pull --ff-only`
  on `main` only when authorised (rare; coordinator decision).
- `git push` (without `--force`) of your own branch's new commits.

## OTHER WORKTREE DISCIPLINE

Keep worktrees on disk permanently. Do not move, delete, or rewrite
another agent's workspace. Report stale or merged worktrees as
inventory only.

Name branches `<type>/<issue>-<subject>` with `feature`, `bug`, or
`chore`. Name worktree folders with the slash flattened to a dash.

Provision new worktrees from main. Create the branch, push upstream
immediately, sync all dependency groups, refresh the lockfile,
install vaultspec, then return to main.

## CONSEQUENCES

A forbidden-command run by a dispatched agent is logged as a
security incident in the audit trail, escalated to the user, and
the responsible agent's session is treated as compromised — its
output is reviewed for unrelated destructive side-effects before
any of its work is trusted. Repeat offences across the agent fleet
trigger a coordinator-level review of dispatch briefs.
