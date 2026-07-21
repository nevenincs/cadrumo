---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-17'
step_id: 'S311'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# ambient-index commit discipline violation: peer agent's commit 38d82ce95 absorbed coder1's S296 working tree via git add -A or equivalent

## Scope

- `explicit-pathspec staging is mandatory per the parallel-worktree explicit_path_staging memory`
- `brief subsequent peer dispatches with stronger language`
- `.vaultspec/`

## Description

- Record the ambient-index commit-discipline incident (commit 38d82ce95 absorbed a peer's working tree via a non-explicit stage) as a closed process finding.
- Confirm the durable lesson is codified as the standing project rule `subagent-commits-require-explicit-pathspec` (every dispatched agent commits with an explicit `git commit -- <pathspec>` naming only files it authored, and verifies `git diff --cached` carries zero foreign markers before committing).
- No production-code change: the incident is process, not code; the code content stands and rolling it back would itself be destructive.

## Outcome

Doc-only closure. The lesson that would otherwise live only in this Step is now a session-inherited rule, so the constraint binds every future dispatch rather than this one campaign. Companion rules: `uncommitted-wip-is-not-orphaned`, `aeat-git-worktree-safety`.

## Notes

Closed by codification (the rule already ships in `.vaultspec/rules/rules/`), not by a commit. No rollback of 38d82ce95 is attempted because reverting a peer commit is itself a forbidden destructive operation.
