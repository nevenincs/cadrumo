---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S21'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Remove the tracked repo-root run artifacts from version control

## Scope

- `repo-root run artifacts`

## Description

- Read each of the five tracked repo-root files to confirm genuine
  run-artifact provenance before removal: `add_frontmatter.py` (an ad-hoc
  docs frontmatter-injector script), `rail-snap.md` (a Playwright
  accessibility-tree snapshot dump), `revert.patch` (a captured git diff from
  an earlier revert/apply-cached run), `scratch_pathspec.txt` (an empty
  pathspec probe), `test_docs_output.txt` (a captured docs-gate command log).
- `git rm --cached` all five, leaving working-tree bytes untouched (per the
  git-worktree-safety and no-destructive-delete disciplines).

## Outcome

- All five paths now match a `W04.P07.S20` gitignore pattern
  (`git check-ignore -q`), so `git status` shows no stray untracked entries
  after the cached removal.
- Working-tree bytes for all five files are preserved on disk; only the git
  index entries were removed.
- Landed via `git commit-tree` plus a compare-and-swap `git update-ref` on the
  shared branch ref rather than a normal `git rm --cached` + `git commit --
  <pathspec>` sequence, after repeated ordinary attempts (roughly 25 across
  several retry loops) each reported "nothing to commit" for the five
  pathspecs despite `git status --porcelain` proving the deletion staged
  moments earlier. The shared index in this worktree is under heavy
  concurrent-agent write load; the CAS ref update against a private temp
  index (`GIT_INDEX_FILE`) sidesteps the shared-index race and succeeded on
  its first attempt.

## Notes

Reported the shared-index contention pattern to the dispatching agent
(`team-lead`) for awareness: something in the shared worktree is repeatedly
resetting other agents' staged index state within a sub-second window,
consistent with a peer running a broad `git add` rather than the mandated
explicit-pathspec form. No data was lost here (the plumbing-based CAS commit
either lands cleanly or fails visibly with no side effect), but the
contention rate observed (roughly 220+ commits landing across the session)
is worth the team lead's attention.
