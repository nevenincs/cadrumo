# Worktree safety, commits, and red tree-wide gates — ABSOLUTE

Many concurrent agents hold uncommitted work in this shared tree at all times.
Any destructive Git operation can silently destroy hours of a peer's work.

## Forbidden, with no debugging exception

`git stash` (any form), `git reset` (any form, including with a pathspec),
`git checkout <path>`/`<branch>`, `git switch`, `git restore`, `git clean`,
`git rebase`, `git commit --amend`, `git revert` of a commit that is not your own
from this session, `git push --force`, `git worktree remove`/`prune`,
`git branch -D`, and `rm -rf` against any tracked path.

Also forbidden: deleting, moving, truncating or renaming anything under `.git/`,
**including `.git/index.lock`**. Diagnose a held lock by its mtime — advancing
means contention, frozen means the holder died — and report it either way.

If you are blocked and reaching for these, STOP and report. "Blocked because I
would need to stash" is acceptable; stashing is not. Investigate by inspection
(`git diff`, `git log`, `git show HEAD:<path>`); to compare against a committed
version, copy the working file aside, `Write` the HEAD bytes in place, test,
restore.

## Commits take more than you name

**A bare `git commit` takes the entire index**, including every peer file staged
by another agent — `git add -- <paths>` does not protect you, the *commit* needs
the pathspec. **`git commit -- <paths>` takes WORKING-TREE content** for those
paths, which silently defeats an apply-cached staging.

- **Clean, unentangled file:** go straight to `git commit -- <path>`. Do not
  `git add` at all; the add window is itself exposure.
- **File carrying peer WIP:** use the apply-cached drive below, then a
  **verified-index bare commit**.
- **Verify AFTER, never before.** A pre-commit `git diff --cached` is TOCTOU.
  Cite `git show <sha> --numstat`.
- Before pathspec-committing any `__init__.py` or package facade, diff it against
  HEAD — a facade accumulates several agents' edits.
- Never over-stage and then "undo" with `git reset`; there is no reset escape
  hatch.

## Uncommitted work with no reachable owner is live peer WIP

Never discard or overwrite it — not with a destructive verb, and not with a
`Write`-from-HEAD either; the mechanism is irrelevant. Re-appearance after a
discard is proof of life. A prior authorization to discard an *orphaned* change
does not extend to a *proven-live* one.

**The apply-cached drive** is the sanctioned way to land your own change in a
contended file: `git show HEAD:<path>` into a scratch copy (capture bytes, never
decoded text); apply only your edits to it; produce a HEAD-anchored own-only
patch with `git diff` and write it in binary; `git apply --cached --check` then
`git apply --cached`; confirm the staged set carries zero foreign markers,
derived from the patch itself by allowlist; then commit the index. Unstage with
`git apply --cached --reverse`.

It updates the index and HEAD and **never the working tree**, so afterwards the
working copy is stale and looks like ordinary WIP. Always build an edit from
`git show HEAD:<file>`, never from the working copy, on any file peers touch.

A whole-tree-validating change (a registry re-stamp) validates against the dirty
tree, so it genuinely waits. Hold; do not force.

`git push` carries all ancestors — check `git log origin..HEAD` first.

## A red full-tree gate needs an owner

When a required full-tree gate is red, record the exact current failure
signatures and distinguish owner-surface failures from unrelated peer churn
before marking a step complete. Without owner triage, a closeout either falsely
claims green or opportunistically edits peer work.

## How

- **Good:** capture the gate output to a log, extract the import and error
  summaries, name the affected modules, and keep the step open when failures are
  outside the feature surface.
- **Good:** if the failing signatures are in the feature's own files or
  contracts, fix them and re-run the full-tree gate.
- **Bad:** marking a full-tree verification step complete because focused tests
  passed while the repository-wide gate still has untriaged collection errors.
- **Bad:** patching unrelated support modules just to make a closeout gate pass
  when those files belong to active peer campaigns.

## Worktree inventory

Keep worktrees on disk permanently; never move, delete or rewrite another agent's
workspace. Report stale or merged worktrees as inventory only. Name branches
`<type>/<issue>-<subject>` with `feature`, `bug`, or `chore`, and worktree folders
with the slash flattened to a dash. Provision from main: create the branch, push
upstream, sync dependency groups, refresh the lockfile, install vaultspec, return
to main.

A forbidden command run by a dispatched agent is a security incident: it is
escalated, and that agent's output is reviewed for unrelated destructive side
effects before any of its work is trusted.
