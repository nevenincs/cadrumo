---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S311'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S311 and 2026-05-26-cross-domain-continuity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The ambient-index commit discipline violation: peer agent's commit 38d82ce95 absorbed coder1's S296 working tree via git add -A or equivalent and ## Scope

- `explicit-pathspec staging is mandatory per the parallel-worktree explicit_path_staging memory`
- `brief subsequent peer dispatches with stronger language`
- `.vaultspec/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
